// Run only against a fresh demo installation; supply DEMO_URL and DEMO_PASSWORD.
import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';

const base=process.env.DEMO_URL||'http://127.0.0.1:8080';
const password=process.env.DEMO_PASSWORD;
if(!password) throw new Error('Set DEMO_PASSWORD for your isolated demo installation');
const screenshots=resolve(process.env.SCREENSHOT_DIR||'../docs/images');
await mkdir(screenshots,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const errors=[];
context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
await context.route('**/*',route=>{
  if(new URL(route.request().url()).origin!==new URL(base).origin){
    errors.push('Unexpected external browser request');return route.abort();
  }
  return route.continue();
});
const page=await context.newPage();
try {
  await page.goto(base);
  await page.getByLabel('Utilizador',{exact:true}).fill('admin');
  await page.getByLabel('Palavra-passe',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Entrar no agendador'}).click();
  await page.getByRole('heading',{name:'Tudo a seu tempo.'}).waitFor();
  await page.getByText('Modo de demonstração',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Nova mensagem',exact:true}).click();
  await page.getByLabel('Destinatário',{exact:true}).fill('+12025550123');
  await page.getByLabel('Nome opcional').fill('Pessoa fictícia');
  await page.locator('textarea').fill('Lembrete de demonstração — não será enviado.');
  await page.locator('input[type=date]').first().fill('2099-11-20');
  await page.getByLabel('Confirmo consentimento',{exact:false}).check();
  await page.getByRole('button',{name:'Pré-visualizar mensagem'}).click();
  await page.getByText('PARA Pessoa fictícia').waitFor();
  await page.screenshot({path:resolve(screenshots,'compose-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'Guardar rascunho'}).click();
  await page.getByText('Mensagem guardada com segurança.').waitFor();
  await page.locator('.sidebar nav').getByRole('button',{name:/Rascunhos/}).click();
  await page.locator('.message-row').filter({hasText:'Pessoa fictícia'}).last().click();
  await page.getByRole('button',{name:'Editar / reagendar'}).click();
  await page.getByLabel('Repetição',{exact:false}).selectOption('daily');
  await page.getByRole('button',{name:'Agendar mensagem',exact:true}).click();
  await page.getByText('Mensagem guardada com segurança.').waitFor();
  await page.locator('.sidebar nav').getByRole('button',{name:'Agenda',exact:true}).click();
  await page.locator('.message-row').filter({hasText:'Pessoa fictícia'}).last().waitFor();
  await page.getByRole('button',{name:'Calendário',exact:true}).click();
  await page.locator('.calendar-grid').waitFor();
  await page.locator('.toast').waitFor({state:'hidden'});
  await page.screenshot({path:resolve(screenshots,'calendar-desktop.png'),fullPage:true});
  await page.locator('.sidebar nav').getByRole('button',{name:'Início',exact:true}).click();
  await page.screenshot({path:resolve(screenshots,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:393,height:852});
  await page.screenshot({path:resolve(screenshots,'mobile.png'),fullPage:false});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth))throw new Error('Mobile horizontal overflow');
  await page.locator('.mobile-nav').getByRole('button',{name:'Nova',exact:true}).click();
  await page.getByLabel('Destinatário',{exact:true}).fill('demo@example.invalid');
  await page.getByRole('button',{name:'Email',exact:true}).click();
  await page.getByLabel('Destinatário',{exact:true}).fill('demo@example.invalid');
  await page.getByLabel('Assunto',{exact:true}).fill('Exemplo fictício');
  await page.locator('textarea').fill('Mensagem fictícia guardada no telemóvel.');
  await page.getByLabel('Confirmo consentimento',{exact:false}).check();
  await page.screenshot({path:resolve(screenshots,'compose-mobile.png'),fullPage:true});
  await page.getByRole('button',{name:'Guardar rascunho'}).click();
  await page.getByText('Mensagem guardada com segurança.').waitFor();
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS: login, demo banner, draft/create/edit/schedule, recurrence, preview, calendar, desktop/mobile, no external requests or JavaScript errors.');
} finally {
  await browser.close();
}
