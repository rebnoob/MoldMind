export const config = {
  api: {
    url: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    timeout: 30000,
  },
  upload: {
    maxFileSizeMb: 100,
    acceptedExtensions: [".step", ".stp"],
  },
  viewer: {
    defaultPullDirection: [0, 0, 1] as [number, number, number],
    tessellationDeflection: 0.1,
  },
  dfm: {
    scoringWeights: {
      critical: 15,
      warning: 7,
      info: 2,
    },
  },
};

export type Config = typeof config;
