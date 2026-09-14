/**
 * Motus CRM proxy — "прослойка" between the website's forms and whatever
 * CRM actually receives the lead.
 *
 * WHY THIS EXISTS (2026-09-07, owner's explicit request): the site's two
 * forms (order.html's detailed request form, index-hero-demo.html's quick
 * callback form) used to fetch() straight into the Google Sheets Apps
 * Script Web App URL. That meant switching CRM (e.g. to Bitrix24 someday)
 * would require editing and redeploying the SITE itself. This proxy is a
 * separate Apps Script project with its OWN Web App URL — the site is
 * wired to THIS url and never touches it again. Where the lead actually
 * goes next is decided entirely inside this one file.
 *
 * HOW TO ADD/SWITCH A DESTINATION:
 *   Add a new function shaped like the ones below (takes the parsed lead
 *   object, sends it wherever), then add/remove a call to it inside
 *   dispatchLead_(). Multiple destinations can run at once (e.g. keep
 *   writing to the Sheet AND start sending to Bitrix24 in parallel while
 *   you verify the new CRM before cutting over) — each destination call is
 *   wrapped in try/catch so one failing destination never blocks another.
 *
 * DEPLOYMENT (one-time, and again after any edit to this file):
 *   Google Sheets → any new/blank spreadsheet → Extensions → Apps Script
 *   → paste this file's content → Deploy → New deployment → Web app →
 *   Execute as: Me, Who has access: Anyone → copy the resulting /exec URL
 *   → give it to Claude to wire into order.html's CRM_WEBHOOK_URL and
 *   index-hero-demo.html's QUICK_FORM_CRM_WEBHOOK_URL (both should point
 *   at THIS proxy's URL, not the Sheet's own webhook URL directly).
 *
 *   This does NOT need to live bound to the "MOTUS CRM — Рабочая" sheet
 *   itself — a separate small script project keeps this proxy's own
 *   redeploys from ever touching the real CRM script by accident. A blank
 *   throwaway spreadsheet just to host the Apps Script project is fine.
 */

// ---------- current destination(s) ----------

// The MOTUS CRM Sheet's own Apps Script webhook — same URL the site used
// to call directly. Moving forward this is the ONLY place that URL is
// referenced; if the Sheet's webhook is ever redeployed and gets a new
// URL, update it here only, not in the site's HTML files.
var SHEETS_CRM_WEBHOOK_URL = 'https://script.google.com/macros/s/AKfycbyi-msy1byt3bCdlntUw_9kikOylxlxtqBddF9pdKSkYSkxBykNwk_0zJZF-f7i6giS/exec';

/**
 * Sends the lead to Google Sheets, unchanged — this proxy currently just
 * passes the payload straight through, since that's the only destination
 * that exists yet. Swap/extend this function's body (not its signature)
 * when the Sheets webhook's own expected shape changes.
 */
function sendToSheets_(lead){
  UrlFetchApp.fetch(SHEETS_CRM_WEBHOOK_URL, {
    method: 'post',
    contentType: 'text/plain;charset=utf-8',
    payload: JSON.stringify(lead),
    muteHttpExceptions: true, // read the response ourselves instead of throwing
  });
}

/**
 * TEMPLATE for a future second destination — not wired up yet, left here
 * as a starting point for whenever a real switch happens. Delete this
 * comment block and fill in the real request shape once there's an actual
 * Bitrix24 (or other CRM) webhook URL/API to send to.
 *
 * function sendToBitrix24_(lead){
 *   var BITRIX_WEBHOOK_URL = 'https://yourcompany.bitrix24.com/rest/1/XXXXXXX/crm.lead.add.json';
 *   UrlFetchApp.fetch(BITRIX_WEBHOOK_URL, {
 *     method: 'post',
 *     contentType: 'application/json',
 *     payload: JSON.stringify({
 *       fields: {
 *         TITLE: (lead.intent === 'cyprus' ? 'Кипр: ' : 'Япония: ') + (lead.model || ''),
 *         NAME: lead.firstName,
 *         LAST_NAME: lead.lastName,
 *         PHONE: [{VALUE: lead.phone, VALUE_TYPE: 'WORK'}],
 *         // ...map the rest of `lead`'s fields to Bitrix24's own field names
 *       }
 *     }),
 *     muteHttpExceptions: true,
 *   });
 * }
 */

/**
 * The one place that decides where a lead goes. Each destination call is
 * isolated in its own try/catch so a failure in one (e.g. Bitrix24 down)
 * never stops the others (e.g. the Sheet) from receiving the lead.
 */
function dispatchLead_(lead){
  try {
    sendToSheets_(lead);
  } catch (err) {
    Logger.log('sendToSheets_ failed: ' + err);
  }

  // When a second destination exists, add it the same way:
  // try { sendToBitrix24_(lead); } catch (err) { Logger.log('sendToBitrix24_ failed: ' + err); }
}

/**
 * Entry point Apps Script calls for every POST to this Web App's /exec
 * URL. Mirrors the request shape the site already sends (raw JSON string
 * as the body, Content-Type text/plain — see order.html/index-hero-demo.html
 * comments for why text/plain: it avoids a CORS preflight Apps Script Web
 * Apps can't answer).
 */
function doPost(e){
  var lead;
  try {
    lead = JSON.parse(e.postData.contents);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok: false, error: 'invalid JSON'}))
      .setMimeType(ContentService.MimeType.JSON);
  }

  dispatchLead_(lead);

  // The site's fetch() calls are fire-and-forget (doesn't read this
  // response — Apps Script Web Apps send no CORS headers back to a
  // cross-origin fetch, so the site can't reliably read the response body
  // anyway), but returning something valid here still matters for anyone
  // testing this URL directly (curl, Postman, etc).
  return ContentService.createTextOutput(JSON.stringify({ok: true}))
    .setMimeType(ContentService.MimeType.JSON);
}
