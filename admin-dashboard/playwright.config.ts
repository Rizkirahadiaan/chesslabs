import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,retries:0,timeout:60000,use:{baseURL:process.env.CHESSLAB_E2E_URL||'http://localhost:3000',headless:true,channel:'chrome',viewport:{width:1440,height:1000},trace:'off'},reporter:[['list'],['json',{outputFile:'../work/e2e-results.json'}]]});
