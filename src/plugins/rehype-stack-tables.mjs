import { visit } from 'unist-util-visit';

// Tables of three or more columns are stacked on phones (see .kz-stack in global.css):
// each row becomes a block and each cell is labelled with its column header, so long
// prose cells keep the full width instead of being squeezed into slivers.
const MIN_COLUMNS = 3;

function text(node) {
  if (node.type === 'text') return node.value;
  return (node.children || []).map(text).join('');
}

function child(node, tagName) {
  return (node.children || []).find((c) => c.type === 'element' && c.tagName === tagName);
}

function cells(row) {
  return (row.children || []).filter((c) => c.type === 'element' && (c.tagName === 'td' || c.tagName === 'th'));
}

export default function rehypeStackTables() {
  return (tree) => {
    visit(tree, 'element', (node) => {
      if (node.tagName !== 'table') return;
      const headRow = child(child(node, 'thead') || {}, 'tr');
      const body = child(node, 'tbody');
      if (!headRow || !body) return;
      const heads = cells(headRow).map((c) => text(c).trim());
      if (heads.length < MIN_COLUMNS) return;
      node.properties.className = [...(node.properties.className || []), 'kz-stack'];
      for (const row of body.children || []) {
        if (row.type !== 'element' || row.tagName !== 'tr') continue;
        cells(row).forEach((cell, i) => {
          if (heads[i]) cell.properties.dataLabel = heads[i];
        });
      }
    });
  };
}
