export type MediaError={provider_http_status:number;quota_limit:number|null;retry_after_seconds:number|null};

export default function MediaFailure({error}:{error:MediaError}){
 return <div role="alert" className="action-bot-error"><strong>Gemini rejected this media request (HTTP {error.provider_http_status}).</strong>
  <p>{error.provider_http_status===429?'Check the selected model’s quota before starting a new reviewed request.':'Check the request and selected media model before starting a new reviewed request.'}</p>
  {error.quota_limit===0&&<p>Gemini reports a quota limit of 0 for this request.</p>}
  {error.quota_limit!==0&&error.retry_after_seconds!=null&&<p>Provider retry delay: {error.retry_after_seconds} seconds.</p>}
  <small>No automatic model retry was made.</small></div>;
}
