import {type Locator, type Page} from '@playwright/test';
import {expect, installInputEvidence, readInputEvidence, test, touchPath, validateInputEvidence} from '@xenorepo/browser-testing';

async function mouseDrag(page:Page,source:Locator,target:Locator){
  await target.scrollIntoViewIfNeeded();await source.scrollIntoViewIfNeeded();
  const from=await source.boundingBox(),to=await target.boundingBox();
  if(!from||!to)throw new Error('Calendar drag path has no bounds');
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();
  await page.mouse.move(from.x+from.width/2+12,from.y+from.height/2,{steps:2});
  await page.mouse.move(to.x+to.width/2,to.y+to.height/2,{steps:5});await page.mouse.up();
}
function nextDate(value:string){const result=new Date(`${value}T12:00:00Z`);result.setUTCDate(result.getUTCDate()+1);return result.toISOString().slice(0,10);}

test('[acceptance] creates, edits, drags, reloads, and deletes a durable event',async({page},testInfo)=>{
  await installInputEvidence(page);await page.goto('/');
  await expect(page.getByText('CALENDAR // 01')).toBeVisible();await expect(page.locator('calendar-console')).toBeInViewport();await expect(page.locator('.day')).toHaveCount(42);
  const title=`Commitment ${Date.now()}`;
  await page.getByRole('button',{name:'ADD',exact:true}).click();await page.getByLabel('Title').fill(title);
  await page.getByLabel('Location').fill('Studio B');await page.getByLabel('Notes').fill('Bring the planning ledger');
  const initialDate=await page.getByLabel('Date').inputValue();await page.getByRole('button',{name:'SAVE',exact:true}).click();
  await page.locator('.agenda-row').filter({hasText:title}).click();await page.getByLabel('Title').fill(`${title} edited`);
  await page.getByLabel('Start').fill('13:15');await page.getByLabel('End').fill('14:45');
  await page.getByRole('button',{name:'SAVE',exact:true}).click();const edited=`${title} edited`;
  await expect(page.locator('.agenda-row').filter({hasText:edited})).toContainText('13:15');
  const cells=page.locator('.day');const sourceIndex=await cells.evaluateAll((values,date)=>values.findIndex(value=>(value as HTMLElement).dataset.date===date),initialDate);
  const destination=cells.nth(sourceIndex+1),destinationDate=await destination.getAttribute('data-date');
  const modality=testInfo.project.name==='narrow-viewport-chromium'?'touch':'mouse';
  if(modality==='touch'){
    await destination.scrollIntoViewIfNeeded();
    const source=await page.locator('.agenda-row').filter({hasText:edited}).locator('.drag-handle').boundingBox(),target=await destination.boundingBox();
    if(!source||!target)throw new Error('Touch drag path has no bounds');
    await touchPath(page,[{x:source.x+source.width/2,y:source.y+source.height/2},{x:source.x+source.width/2+12,y:source.y+source.height/2},{x:target.x+target.width/2,y:target.y+target.height/2}]);
  }else await mouseDrag(page,page.locator('.chip').filter({hasText:edited}),destination);
  await expect(page.locator('x-status-indicator')).toHaveAttribute('label',`Moved “${edited}”`);
  const evidence=await readInputEvidence(page);expect(validateInputEvidence(evidence,modality)).toMatchObject({accepted:true});
  await testInfo.attach('input-evidence.json',{body:JSON.stringify({schemaVersion:1,modality,records:evidence},null,2),contentType:'application/json'});
  const authoritative=await page.request.get(`/api/calendar?start=${destinationDate}&end=${nextDate(destinationDate!)}`);
  expect(authoritative.ok()).toBe(true);expect((await authoritative.json()).events).toEqual([expect.objectContaining({title:edited,date:destinationDate,location:'Studio B'})]);
  await page.reload();await page.locator(`.day[data-date="${destinationDate}"]`).click();
  await expect(page.locator('.agenda-row').filter({hasText:edited})).toBeVisible();
  await page.locator('.agenda-row').filter({hasText:edited}).click();page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'DELETE',exact:true}).click();await expect(page.locator('.agenda-row').filter({hasText:edited})).toHaveCount(0);
});
