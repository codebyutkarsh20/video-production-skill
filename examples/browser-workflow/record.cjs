// npm install --no-save playwright; npx playwright install chromium
// NODE_PATH may point to a host's installed packages. No host-specific path is bundled.
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const {pathToFileURL}=require('node:url');
(async()=>{
 const out=path.resolve(process.argv[2]||'artifacts/browser-workflow');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:720},recordVideo:{dir:out,size:{width:1280,height:720}}});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
  await page.mouse.move(950,300);await page.waitForTimeout(1200);
  const add=page.getByRole('button',{name:'Add employee'});const box=await add.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2,{steps:30});await page.waitForTimeout(400);await add.click();
  await page.waitForTimeout(650);await page.locator('#name').pressSequentially('Meera Nair',{delay:85});
  await page.locator('#email').pressSequentially('meera@example.com',{delay:60});
  await page.locator('#team').selectOption('People');await page.waitForTimeout(900);
  const save=page.getByRole('button',{name:'Save employee'});const sb=await save.boundingBox();
  await page.mouse.move(sb.x+sb.width/2,sb.y+sb.height/2,{steps:30});await page.waitForTimeout(350);await save.click();
  if(await page.locator('#count').textContent()!=='3')throw Error('Employee count did not update');
  if(!(await page.locator('#notice').textContent()).includes('Meera Nair was saved'))throw Error('Saved result missing');
  if(errors.length)throw Error(errors.join('\n'));
  await page.screenshot({path:path.join(out,'saved-result.png')});await page.waitForTimeout(2600);
  const video=page.video();await context.close();await video.saveAs(path.join(out,'workflow.webm'));
  fs.writeFileSync(path.join(out,'browser-checks.json'),JSON.stringify({actual_browser_flow:true,employee_saved:true,count:3,page_errors:errors,external_delivery:false,source:'Original fictional browser example'},null,2));
  console.log(JSON.stringify({output:out,checks:'actual save and browser assertions passed'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
