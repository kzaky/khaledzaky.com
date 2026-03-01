import { visit } from 'unist-util-visit';
import fs from 'node:fs';
import path from 'node:path';

/**
 * Rehype plugin that inlines local SVG images at build time.
 * Replaces <img src="/postimages/charts/foo.svg"> with the raw <svg> element
 * so it lives in the DOM and can respond to the page's .dark class.
 */
export default function rehypeInlineSvgs() {
  return (tree) => {
    visit(tree, 'element', (node, index, parent) => {
      if (
        node.tagName !== 'img' ||
        !node.properties?.src ||
        !node.properties.src.endsWith('.svg') ||
        node.properties.src.startsWith('http')
      ) {
        return;
      }

      const svgPath = path.join(process.cwd(), 'public', node.properties.src);
      if (!fs.existsSync(svgPath)) return;

      const svgContent = fs.readFileSync(svgPath, 'utf-8');

      // Parse the SVG into a hast-compatible node
      const alt = node.properties.alt || '';

      // Build a raw HTML node — simplest and most reliable approach
      parent.children[index] = {
        type: 'raw',
        value: `<figure role="img" aria-label="${alt.replace(/"/g, '&quot;')}">${svgContent}</figure>`,
      };
    });
  };
}
