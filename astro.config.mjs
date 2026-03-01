import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import rehypeLazyImages from './src/plugins/rehype-lazy-images.mjs';
export default defineConfig({
  site: 'https://khaledzaky.com',
  integrations: [mdx(), sitemap({
    serialize(item) {
      // Remove trailing slash for consistency
      return item;
    },
  })],
  vite: {
    plugins: [tailwindcss()],
  },
  output: 'static',
  markdown: {
    rehypePlugins: [rehypeLazyImages],
    shikiConfig: {
      themes: {
        light: 'github-light',
        dark: 'github-dark',
      },
    },
  },
});
