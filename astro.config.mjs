import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwind from '@astrojs/tailwind';
import rehypeLazyImages from './src/plugins/rehype-lazy-images.mjs';

export default defineConfig({
  site: 'https://khaledzaky.com',
  integrations: [mdx(), sitemap(), tailwind()],
  output: 'static',
  markdown: {
    rehypePlugins: [rehypeLazyImages],
  },
});
