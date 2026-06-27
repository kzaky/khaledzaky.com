import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import rehypeLazyImages from './src/plugins/rehype-lazy-images.mjs';
export default defineConfig({
  site: 'https://khaledzaky.com',
  integrations: [
    mdx(),
    sitemap({
      serialize(item) {
        if (item.url === 'https://khaledzaky.com/') {
          return { ...item, priority: 1.0, changefreq: 'weekly' };
        }
        if (item.url.includes('/blog/category/')) {
          return { ...item, priority: 0.4, changefreq: 'weekly' };
        }
        if (item.url.includes('/blog/')) {
          return { ...item, priority: 0.8, changefreq: 'monthly' };
        }
        if (item.url === 'https://khaledzaky.com/blog') {
          return { ...item, priority: 0.9, changefreq: 'daily' };
        }
        return { ...item, priority: 0.6, changefreq: 'monthly' };
      },
    }),
  ],
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
