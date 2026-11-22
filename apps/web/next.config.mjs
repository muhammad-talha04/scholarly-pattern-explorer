/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  transpilePackages: ["three", "postprocessing"],
  // The nav calls /timeline "Progress"; let the obvious URL work too.
  redirects: async () => [{ source: "/progress", destination: "/timeline", permanent: true }],
};
