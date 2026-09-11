import { defineConfig } from "allure";

const accessToken = process.env.ALLURE_ACCESS_TOKEN;

if (!accessToken) {
  throw new Error("ALLURE_ACCESS_TOKEN is required to publish a report");
}

export default defineConfig({
  name: process.env.ALLURE_REPORT_NAME ?? "Hardware test report",
  output: "/tmp/allure-report",
  plugins: {
    awesome: {
      options: {
        publish: true,
      },
    },
  },
  allureService: {
    accessToken,
  },
});
