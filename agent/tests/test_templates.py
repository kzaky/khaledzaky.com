"""Structural checks on the CloudFormation templates (agent/template.yaml and
infra/template.yaml) for failures that cfn-lint does not catch: each one either
deleted data, silently stopped logging, or made an alarm that could never fire."""

import re
from pathlib import Path

import yaml

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = AGENT_DIR.parent
INFRA_TEMPLATE = REPO_DIR / "infra" / "template.yaml"

_TAGS = ("!Sub", "!Ref", "!GetAtt", "!Join", "!Select", "!Split", "!ImportValue", "!If",
         "!Equals", "!Not", "!FindInMap", "!Base64", "!Condition", "!And", "!Or")


def _load(path):
    class _CFNLoader(yaml.SafeLoader):
        pass

    def _passthrough(loader, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        return loader.construct_mapping(node, deep=True)

    for tag in _TAGS:
        _CFNLoader.add_constructor(tag, _passthrough)
    return yaml.load(path.read_text(), Loader=_CFNLoader)


def _agent():
    return _load(AGENT_DIR / "template.yaml")


def _infra():
    return _load(INFRA_TEMPLATE)


def _rule_prefix(rule):
    if "Prefix" in rule:
        return rule["Prefix"]
    return (rule.get("Filter") or {}).get("Prefix")


class TestDraftsBucket:
    """The drafts bucket holds config/voice-profile.md and config/voice-references/.
    A lifecycle rule with an empty prefix and a 90-day expiry would have deleted them
    90 days after every deploy uploaded them."""

    def _bucket(self):
        return _agent()["Resources"]["DraftsBucket"]

    def test_every_expiring_rule_is_scoped_to_a_working_prefix(self):
        rules = self._bucket()["Properties"]["LifecycleConfiguration"]["Rules"]
        for rule in rules:
            prefix = _rule_prefix(rule)
            expires = "ExpirationInDays" in rule or "ExpirationDate" in rule
            if expires:
                assert prefix, f"rule {rule['Id']} expires objects bucket-wide (no prefix)"
                assert not prefix.startswith("config"), f"rule {rule['Id']} expires config/"
        prefixes = {_rule_prefix(r) for r in rules}
        for needed in ("drafts/", "charts/", "inbound/", "uploads/", "checkpoints/"):
            assert needed in prefixes, f"{needed} lost its cleanup rule"

    def test_no_rule_touches_config(self):
        for rule in self._bucket()["Properties"]["LifecycleConfiguration"]["Rules"]:
            prefix = _rule_prefix(rule) or ""
            assert prefix and not "config/".startswith(prefix), (
                f"rule {rule['Id']} (prefix {prefix!r}) covers config/"
            )

    def test_versioned_and_retained(self):
        bucket = self._bucket()
        assert bucket["Properties"]["VersioningConfiguration"]["Status"] == "Enabled"
        assert bucket.get("DeletionPolicy") == "Retain"
        assert bucket.get("UpdateReplacePolicy") == "Retain"
        # the name must not change: that would be a replacement of a fixed-name bucket
        assert bucket["Properties"]["BucketName"] == "${AWS::StackName}-drafts"

    def test_cors_for_drop_uploads_is_in_the_template(self):
        rules = self._bucket()["Properties"]["CorsConfiguration"]["CorsRules"]
        assert any("https://khaledzaky.com" in r["AllowedOrigins"] and "PUT" in r["AllowedMethods"]
                   for r in rules)


class TestAgentAlarms:
    def test_per_function_error_alarms_fire_on_one_error(self):
        for logical_id, res in _agent()["Resources"].items():
            props = res.get("Properties", {})
            if res.get("Type") == "AWS::CloudWatch::Alarm" and props.get("MetricName") == "Errors" \
                    and props.get("Namespace") == "AWS/Lambda":
                assert props["EvaluationPeriods"] == 1, logical_id
                assert props["DatapointsToAlarm"] == 1, logical_id
                assert props["Threshold"] == 1, logical_id

    def test_opus_fallback_alarm_matches_the_emitted_dimension(self):
        """common/llm.py puts OpusModelFallback with a ModelId dimension. CloudWatch
        treats each dimension set as its own metric, so a dimensionless alarm watched a
        series nothing ever wrote."""
        llm = (AGENT_DIR / "common" / "llm.py").read_text()
        assert '"Dimensions": [{"Name": "ModelId"' in llm
        props = _agent()["Resources"]["OpusModelFallbackAlarm"]["Properties"]
        dims = {d["Name"]: d["Value"] for d in props.get("Dimensions", [])}
        assert dims == {"ModelId": "OpusModelId"}

    def test_pipeline_timeout_abort_and_dlq_alarms_exist_and_notify(self):
        resources = _agent()["Resources"]
        found = {}
        for res in resources.values():
            props = res.get("Properties", {})
            if res.get("Type") == "AWS::CloudWatch::Alarm":
                found[(props.get("Namespace"), props.get("MetricName"))] = props
        for key in (("AWS/States", "ExecutionsTimedOut"), ("AWS/States", "ExecutionsAborted"),
                    ("AWS/SQS", "ApproximateNumberOfMessagesVisible")):
            assert key in found, f"no alarm on {key}"
            assert found[key].get("AlarmActions"), f"{key} alarm does not notify"
        dlq = found[("AWS/SQS", "ApproximateNumberOfMessagesVisible")]
        assert dlq["Threshold"] == 0 and dlq["ComparisonOperator"] == "GreaterThanThreshold"

    def test_evaluate_log_group_is_gated_so_an_update_cannot_collide(self):
        """/aws/lambda/blog-agent-evaluate already exists (Lambda created it). An
        unconditional AWS::Logs::LogGroup with that name fails the whole update."""
        template = _agent()
        lg = template["Resources"]["EvaluateLogGroup"]
        assert lg["Properties"]["RetentionInDays"] == 30
        assert lg.get("Condition") == "ManageEvaluateLogGroupCond"
        assert lg.get("DeletionPolicy") == "Retain"  # required for import
        assert template["Parameters"]["ManageEvaluateLogGroup"]["Default"] == "false"


class TestAgentDeployScript:
    def test_template_is_not_staged_in_a_bucket_the_stack_creates(self):
        deploy = (AGENT_DIR / "deploy.sh").read_text()
        assert '--s3-bucket "${STACK_NAME}-drafts"' not in deploy
        assert '--s3-bucket "$ARTIFACTS_BUCKET"' in deploy
        assert "create-bucket" in deploy


class TestInfraTemplate:
    def test_fits_the_inline_template_body_limit(self):
        """infra/deploy.sh passes the template inline (validate-template
        --template-body, deploy with no --s3-bucket); CloudFormation caps that at
        51,200 bytes."""
        assert len(INFRA_TEMPLATE.read_bytes()) < 51200

    def test_cloudtrail_has_its_own_bucket_with_a_cloudtrail_policy(self):
        resources = _infra()["Resources"]
        trail = resources["ManagementTrail"]
        assert trail["Properties"]["S3BucketName"] == "CloudTrailLogsBucket"
        assert "blog-agent-drafts" not in str(trail)
        assert trail.get("DependsOn") == "CloudTrailLogsBucketPolicy"
        bucket = resources["CloudTrailLogsBucket"]
        assert bucket["DeletionPolicy"] == "Retain"
        assert bucket["Properties"]["VersioningConfiguration"]["Status"] == "Enabled"
        pab = bucket["Properties"]["PublicAccessBlockConfiguration"]
        assert all(pab[k] is True for k in ("BlockPublicAcls", "BlockPublicPolicy",
                                             "IgnorePublicAcls", "RestrictPublicBuckets"))
        for rule in bucket["Properties"]["LifecycleConfiguration"]["Rules"]:
            assert rule.get("ExpirationInDays", 365) >= 365
        stmts = resources["CloudTrailLogsBucketPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        allows = [s for s in stmts if s["Effect"] == "Allow"]
        assert {s["Action"] for s in allows} == {"s3:GetBucketAcl", "s3:PutObject"}
        for s in allows:
            assert s["Principal"] == {"Service": "cloudtrail.amazonaws.com"}
            source_arn = s["Condition"]["StringEquals"]["aws:SourceArn"]
            assert source_arn.endswith(":trail/management-events")

    def test_csp_keeps_drop_endpoints_and_adds_hardening(self):
        policy = _infra()["Resources"]["SecurityHeadersPolicy"]["Properties"]["ResponseHeadersPolicyConfig"]
        csp = policy["SecurityHeadersConfig"]["ContentSecurityPolicy"]["ContentSecurityPolicy"]
        directives = {d.split()[0]: d.split()[1:] for d in (x.strip() for x in csp.split(";")) if d}
        drop = (REPO_DIR / "src" / "pages" / "drop.astro").read_text()
        api_origin = re.search(r"https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com", drop).group(0)
        assert api_origin in directives["connect-src"], "redeploy would break /drop's API calls"
        assert "https://blog-agent-drafts.s3.us-east-1.amazonaws.com" in directives["connect-src"]
        assert "https://blog-agent-drafts.s3.amazonaws.com" in directives["connect-src"]
        assert directives["object-src"] == ["'none'"]
        assert directives["base-uri"] == ["'self'"]
        assert directives["form-action"] == ["'self'"]
        assert directives["frame-ancestors"] == ["'none'"]

    def test_policy_and_function_names_are_valid_cloudfront_names(self):
        """CloudFront rejects a dot in policy and function names, which is why every
        CFN update of the headers policy failed with "Invalid request provided"."""
        resources = _infra()["Resources"]
        names = [resources["SecurityHeadersPolicy"]["Properties"]["ResponseHeadersPolicyConfig"]["Name"]]
        names += [r["Properties"]["Name"] for r in resources.values()
                  if r.get("Type") == "AWS::CloudFront::Function"]
        for name in names:
            assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name), name

    def test_xss_protection_off_and_no_site_wide_robots_header(self):
        cfg = _infra()["Resources"]["SecurityHeadersPolicy"]["Properties"]["ResponseHeadersPolicyConfig"]
        xss = cfg["SecurityHeadersConfig"]["XSSProtection"]
        assert xss["Protection"] is False and "ModeBlock" not in xss
        headers = [i["Header"].lower() for i in cfg["CustomHeadersConfig"]["Items"]]
        assert "x-robots-tag" not in headers

    def test_cloudfront_functions_redirect_and_noindex_drop(self):
        resources = _infra()["Resources"]
        assert "IndexRewriteFunction" not in resources
        req = resources["ViewerRequestFunction"]["Properties"]["FunctionCode"]
        assert "www.khaledzaky.com" in req and "'https://khaledzaky.com'" in req
        assert "'/feed.xml'" in req and "redirect('/rss.xml')" in req
        assert "redirect('/trust/')" in req
        assert "statusCode: 301" in req
        resp = resources["ViewerResponseFunction"]["Properties"]["FunctionCode"]
        assert "'x-robots-tag'" in resp and "noindex, nofollow" in resp
        assert (REPO_DIR / "src" / "pages" / "rss.xml.js").exists()
        assoc = resources["Distribution"]["Properties"]["DistributionConfig"]["DefaultCacheBehavior"][
            "FunctionAssociations"]
        assert {a["EventType"]: a["FunctionARN"] for a in assoc} == {
            "viewer-request": "ViewerRequestFunction.FunctionARN",
            "viewer-response": "ViewerResponseFunction.FunctionARN",
        }

    def test_dashboard_alarm_arns_name_real_alarms(self):
        body = _infra()["Resources"]["InfraDashboard"]["Properties"]["DashboardBody"]
        named = set(re.findall(r":alarm:([A-Za-z0-9_-]+)", body))
        assert "blog-agent-lambda-errors" not in named, "that alarm never existed"
        agent = AGENT_DIR.joinpath("template.yaml").read_text()
        for name in named:
            if name.startswith("blog-agent-"):
                suffix = name[len("blog-agent-"):]
                assert f'AlarmName: !Sub "${{AWS::StackName}}-{suffix}"' in agent, name
        assert "blog-agent-lambda-errors-any" in named
