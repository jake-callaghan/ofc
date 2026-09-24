import config from './playwright.config.js';
export default {
  ...config,
  use: { ...config.use, baseURL: 'http://127.0.0.1:5188', channel: 'chrome' },
  webServer: config.webServer.map((server) => ({
    ...server,
    command: server.command.replaceAll('8011', '8028').replaceAll('5174', '5188'),
    url: server.url.replaceAll('8011', '8028').replaceAll('5174', '5188'),
    env: { ...server.env, ...(server.env.OFC_API_TARGET ? { OFC_API_TARGET: 'http://127.0.0.1:8028' } : {}) },
  })),
};
