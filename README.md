Pymada
======

Pymada is an application to allow distributed running of automated browsers using existing libraries such as Selenium or Puppeteer. It aims to require minimal modification to existing scripts to let them to run in parallel.

## How it works

There are two components, a master API server and agent servers. The master server is responsible for storing all inputs (URLs) and results. It also keeps track of agents and assigns tasks to each agent. The agent servers run in their own container with the browser control software installed. The agent server spawns a process of the browser control script (runner) and allows the runner to get URLs and save results through a simple HTTP interface.

## Features
- CLI for interacting with the master server
- Provisioning of instances with support for multiple providers
- Sets up and runs on a lightweight version of Kubernetes called [K3s](https://k3s.io/)
- CLI access to logging of individual agents
- Support for multiple browser control libraries.

### Supported Agents
- Puppeteer (Chromium)
- Selenium Firefox
- Selenium Chrome


## Example
In order to run a script using Pymada, some minor edits are required. For example on this Puppeteer script:

```javascript
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  const url = 'https://example.com';
  await page.goto(url, {waitUntil: 'networkidle2'});
  const pageTitle = await page.evaluate(() => {
      return document.title;
  });

  await browser.close();

  console.log(pageTitle);
})();
```

You would need to import a `pymada_client` library, change the `const url = 'https://example.com'` line to `const url = await pymada.getTask().url;` and to save the result, change the `console.log(pageTitle)` to `await pymada.saveResult(pageTitle)`. Giving the script:


```javascript
const puppeteer = require('puppeteer');
const pymada = require('pymada_client');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  const url = await pymada.getTask().url;
  await page.goto(url, {waitUntil: 'networkidle2'});
  const pageTitle = await page.evaluate(() => {
      return document.title;
  });

  await browser.close();

  await pymada.saveResult(pageTitle);
})();
```
