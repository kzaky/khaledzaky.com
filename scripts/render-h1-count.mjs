// Count the <h1>s the site's Markdown processor renders for each body. Reads a JSON array
// of strings on stdin, writes a JSON array of counts. agent/tests/fixtures/h1_render_cases.json
// records its answers, so gate.h1_spans is tested against the renderer, not a guess at it.
import { createMarkdownProcessor } from '@astrojs/markdown-remark';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const processor = await createMarkdownProcessor({});
const counts = [];
for (const body of JSON.parse(input)) {
  const { code } = await processor.render(body);
  counts.push((code.match(/<h1\b/gi) || []).length);
}
console.log(JSON.stringify(counts));
