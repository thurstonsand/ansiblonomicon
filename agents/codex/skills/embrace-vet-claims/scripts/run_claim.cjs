#!/usr/bin/env node

const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const readline = require('node:readline');
const { chromium } = require('playwright');

function loadClaim(path) {
  const claim = JSON.parse(fs.readFileSync(path, 'utf8'));
  for (const field of ['invoice_path', 'pet', 'provider', 'invoice_date', 'total', 'diagnosis']) {
    if (!claim[field]) throw new Error(`claim.${field} is required`);
  }
  if (!fs.existsSync(claim.invoice_path)) throw new Error(`invoice not found: ${claim.invoice_path}`);
  if (!/^\d{2}\/\d{2}\/\d{4}$/.test(claim.invoice_date)) throw new Error('claim.invoice_date must be MM/DD/YYYY');
  if (!/^\d+\.\d{2}$/.test(String(claim.total))) throw new Error('claim.total must be digits with two decimal places');
  return claim;
}

function loadCredentials() {
  const item = JSON.parse(execFileSync('op', ['item', 'get', 'Embrace Pet Insurance', '--format', 'json'], { encoding: 'utf8' }));
  const fields = new Map(item.fields.map((field) => [String(field.label || '').toLowerCase(), field.value]));
  const username = fields.get('username') || fields.get('email');
  const password = fields.get('password');
  if (!username || !password) throw new Error('Embrace credentials are incomplete');
  return { username, password };
}

function events() {
  const input = readline.createInterface({ input: process.stdin, terminal: false });
  const lines = [];
  let resolve;
  input.on('line', (line) => {
    if (resolve) {
      const current = resolve;
      resolve = undefined;
      current(line.trim());
    } else {
      lines.push(line.trim());
    }
  });
  return () => lines.length ? Promise.resolve(lines.shift()) : new Promise((done) => { resolve = done; });
}

function emit(event, details = {}) {
  process.stdout.write(`${JSON.stringify({ event, ...details })}\n`);
}

async function logIn(page, nextLine) {
  const { username, password } = loadCredentials();
  await page.goto('https://my.embracepetinsurance.com/login', { waitUntil: 'domcontentloaded' });
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: /log in/i }).click();

  const verificationMethod = page.getByText('Select your verification method', { exact: true });
  if (await verificationMethod.isVisible({ timeout: 5000 }).catch(() => false)) {
    await page.getByText('Email', { exact: true }).click();
    await page.getByRole('button', { name: /send code/i }).click();
    await page.getByText('Check your email', { exact: true }).waitFor();
    emit('mfa_required');
    const code = await nextLine();
    if (!/^\d{8}$/.test(code)) throw new Error('MFA code must contain exactly eight digits');
    for (const [index, digit] of [...code].entries()) {
      await page.locator(`#mfa-digit-${index + 1}`).fill(digit);
    }
    await page.getByRole('button', { name: /verify/i }).click();
  }

  await page.waitForURL('**/home');
  emit('logged_in');
}

async function setInvoiceStore(page, claim) {
  await page.waitForFunction(() => {
    const app = document.querySelector('#__nuxt')?.__vue_app__;
    return app?.config?.globalProperties?.$pinia?._s?.has('submit-claim');
  });
  await page.evaluate(({ invoiceDate, total }) => {
    const app = document.querySelector('#__nuxt').__vue_app__;
    const store = app.config.globalProperties.$pinia._s.get('submit-claim');
    store.invoiceStartDate = invoiceDate;
    store.invoiceEndDate = invoiceDate;
    store.invoiceTotal = total;
  }, { invoiceDate: claim.invoice_date, total: String(claim.total) });
}

async function prepareClaim(page, claim) {
  await page.getByRole('button', { name: /start claim/i }).click();
  await page.waitForURL('**/submit-claim');
  await page.getByText('Start claim', { exact: true }).click();
  await page.waitForURL('**/submit-claim/upload');

  await page.locator('input[type=file]').setInputFiles(claim.invoice_path);
  await page.getByText('Uploaded', { exact: false }).waitFor();
  await page.getByRole('button', { name: /next/i }).click();
  await page.waitForURL('**/submit-claim/details');

  await page.getByText('Near', { exact: true }).waitFor();
  await page.locator('#providers').fill(claim.provider);
  await page.getByText(claim.provider, { exact: true }).click();
  await page.getByText('Single day', { exact: true }).click();
  await page.locator('input[placeholder="$0.00"]').fill(String(claim.total));
  await setInvoiceStore(page, claim);

  await page.getByText(claim.pet, { exact: true }).waitFor();
  await page.getByRole('checkbox').click();
  await page.getByRole('button', { name: /next/i }).click();
  await page.waitForURL('**/submit-claim/diagnosis');

  await page.getByPlaceholder(/search for diagnoses/i).fill(claim.diagnosis);
  await page.getByText(new RegExp(`^${claim.diagnosis}`)).waitFor();
  await page.getByRole('checkbox').click();
  await page.getByRole('button', { name: /next/i }).click();
  await page.waitForURL('**/submit-claim/review');

  const review = await page.locator('body').innerText();
  for (const expected of [claim.provider, claim.invoice_date, `$${claim.total}`, claim.pet, claim.diagnosis, require('node:path').basename(claim.invoice_path)]) {
    if (!review.includes(expected)) throw new Error(`review page is missing expected value: ${expected}`);
  }
  return review;
}

async function submitClaim(page) {
  await page.getByRole('checkbox').click();
  await page.getByRole('button', { name: /submit claim/i }).click();
  await page.waitForURL('**/submit-claim/success');
  await page.getByText('View', { exact: true }).click();
  await page.waitForURL('**/claims/**');
  await page.getByText(/Claim #EC\d+-\d+/).waitFor();
  const text = await page.locator('body').innerText();
  const claimNumber = text.match(/Claim #(EC\d+-\d+)/)?.[1];
  if (!claimNumber) throw new Error('submitted claim number not found');
  return claimNumber;
}

(async () => {
  const path = process.argv[2];
  if (!path) throw new Error('usage: run_claim.cjs <claim.json> [--validate-only]');
  const claim = loadClaim(path);
  if (process.argv.includes('--validate-only')) {
    emit('valid', { claim });
    return;
  }

  const nextLine = events();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await logIn(page, nextLine);
    const review = await prepareClaim(page, claim);
    emit('review_ready', { review });
    if (await nextLine() !== 'SUBMIT') throw new Error('submission approval token was not provided');
    const claimNumber = await submitClaim(page);
    emit('submitted', { claim_number: claimNumber });
  } finally {
    await browser.close();
  }
})().catch((error) => {
  emit('error', { message: error.message });
  process.exit(1);
});
