import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('blog'))
    .filter((post) => !post.data.draft)
    .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());

  return rss({
    title: 'Khaled Zaky',
    description: "Khaled Zaky's blog on agentic AI, platform engineering, cloud architecture, identity, and building real systems that ship.",
    site: context.site,
    items: posts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.date,
      description: post.data.description || '',
      link: `/blog/${post.slug}/`,
      categories: post.data.categories,
    })),
    customData: '<language>en-us</language>',
  });
}
