import {expect, test} from '@xenorepo/browser-testing';

test('[acceptance] opens the calendar service', async ({page}) => {
  await page.goto('/');
  await expect(page.getByText('Calendar Console')).toBeVisible();
});
