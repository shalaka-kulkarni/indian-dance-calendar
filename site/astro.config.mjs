import { defineConfig } from 'astro/config';

// BASE_PATH is set by the GitHub Pages deploy (project sites serve under
// /indian-dance-calendar/). Local builds and root-domain hosts leave it unset.
export default defineConfig({
  output: 'static',
  site: process.env.SITE_URL || 'https://shalaka-kulkarni.github.io',
  base: process.env.BASE_PATH || '/',
});
