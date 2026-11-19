import { createHash, createHmac, randomUUID } from 'node:crypto'

const host = 'dypnsapi.aliyuncs.com'
const algorithm = 'ACS3-HMAC-SHA256'
const sha256 = (value: string) => createHash('sha256').update(value).digest('hex')
const encode = (value: string) => encodeURIComponent(value).replace(/[!'()*]/g, char => `%${char.charCodeAt(0).toString(16).toUpperCase()}`)

export function librarySmsSender() {
  const { WEIBULL_SMS_ACCESS_KEY_ID: keyId, WEIBULL_SMS_ACCESS_KEY_SECRET: keySecret,
    WEIBULL_SMS_SIGN_NAME: signName, WEIBULL_SMS_TEMPLATE_CODE: templateCode } = process.env
  if (!keyId || !keySecret || !signName || !templateCode) return null

  return async (phone: string, code: string) => {
    const query = new URLSearchParams({ CountryCode: '86', PhoneNumber: phone, SignName: signName,
      TemplateCode: templateCode, TemplateParam: JSON.stringify({ code, min: '5' }) })
    query.sort()
    const canonicalQuery = Array.from(query, ([key, value]) => `${encode(key)}=${encode(value)}`).join('&')
    const headers = {
      host,
      'x-acs-action': 'SendSmsVerifyCode',
      'x-acs-content-sha256': sha256(''),
      'x-acs-date': new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      'x-acs-signature-nonce': randomUUID(),
      'x-acs-version': '2017-05-25',
    }
    const fields = Object.keys(headers) as Array<keyof typeof headers>
    const signedHeaders = fields.join(';')
    const canonicalHeaders = fields.map(key => `${key}:${headers[key]}\n`).join('')
    const canonicalRequest = ['POST', '/', canonicalQuery, canonicalHeaders, signedHeaders, headers['x-acs-content-sha256']].join('\n')
    const signature = createHmac('sha256', keySecret).update(`${algorithm}\n${sha256(canonicalRequest)}`).digest('hex')
    const response = await fetch(`https://${host}/?${canonicalQuery}`, {
      method: 'POST', signal: AbortSignal.timeout(8000), redirect: 'error',
      headers: { ...headers, Authorization: `${algorithm} Credential=${keyId},SignedHeaders=${signedHeaders},Signature=${signature}` },
    })
    const data = await response.json()
    if (!response.ok || data?.Code !== 'OK' || data?.Success !== true) {
      const errorCode = typeof data?.Code === 'string' && /^[A-Z][A-Z0-9_.]{1,60}$/i.test(data.Code) ? data.Code : 'UNKNOWN'
      console.error('[library-sms] Provider rejected the SMS', response.status, errorCode)
      throw new Error('SMS delivery rejected')
    }
  }
}
