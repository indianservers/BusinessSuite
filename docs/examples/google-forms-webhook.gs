// Install this as an authorized "From form / On form submit" trigger.
// Set POWER_WEBHOOK_URL and POWER_WEBHOOK_SECRET in Script Properties.
// Adjust the Name/Email/Message question titles to match your own form.
function sendFormToBusinessSuite(event) {
  if (!event || !event.response || !event.source) throw new Error('Use an installable Google Forms submit trigger.');
  const properties = PropertiesService.getScriptProperties();
  const endpoint = properties.getProperty('POWER_WEBHOOK_URL');
  const secret = properties.getProperty('POWER_WEBHOOK_SECRET');
  if (!endpoint || !/^https:\/\//.test(endpoint) || !secret) throw new Error('Configure the secure webhook endpoint and signing secret.');
  const answers = Object.create(null);
  event.response.getItemResponses().forEach(item => { answers[item.getItem().getTitle()] = item.getResponse(); });
  const body = JSON.stringify({form_id:event.source.getId(), response_id:event.response.getId(), email:event.response.getRespondentEmail() || answers.Email || '', name:answers.Name || '', message:answers.Message || '', answers:answers});
  const timestamp = String(Math.floor(Date.now()/1000));
  const nonce = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(event.response.getId()), Utilities.Charset.UTF_8).map(byte => ((byte + 256) % 256).toString(16).padStart(2,'0')).join('');
  const signature = Utilities.computeHmacSha256Signature(timestamp + '.' + nonce + '.' + body, secret, Utilities.Charset.UTF_8).map(byte => ((byte + 256) % 256).toString(16).padStart(2,'0')).join('');
  const response = UrlFetchApp.fetch(endpoint,{method:'post',contentType:'application/json',payload:body,headers:{'x-power-timestamp':timestamp,'x-power-nonce':nonce,'x-power-signature':signature},muteHttpExceptions:true});
  if (![202,409].includes(response.getResponseCode())) throw new Error('Webhook delivery failed with HTTP ' + response.getResponseCode());
}
