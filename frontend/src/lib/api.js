const BASE = import.meta.env.VITE_API_URL || '/api'

async function j(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}

export async function getModel()  { return j(await fetch(`${BASE}/model`)) }
export async function getCanals() { return j(await fetch(`${BASE}/canals`)) }
export async function getJob(id)  { return j(await fetch(`${BASE}/jobs/${id}`)) }
export async function getGeojson(id) { return j(await fetch(`${BASE}/jobs/${id}/geojson`)) }
export async function getBoxes(id) { return j(await fetch(`${BASE}/jobs/${id}/boxes`)) }
export const overviewUrl = (id) => `${BASE}/jobs/${id}/overview`
export const reachImageUrl = (id, rid) => `${BASE}/jobs/${id}/reach/${rid}/image`

export function runPrediction({ canal, alignment, orthophoto, dsm, dtm, onUploadProgress }) {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('orthophoto', orthophoto)
    if (alignment) form.append('alignment', alignment)
    if (canal) form.append('canal', canal)
    if (dsm) form.append('dsm', dsm)
    if (dtm) form.append('dtm', dtm)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/predict`)
    xhr.upload.onprogress = (e) => {
      if (onUploadProgress) onUploadProgress(
        e.lengthComputable ? Math.round(100 * e.loaded / e.total) : null,
        e.loaded, e.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) } catch { resolve({}) }
      } else {
        let d = `Upload failed (HTTP ${xhr.status})`
        try { d = JSON.parse(xhr.responseText).detail || d } catch {}
        reject(new Error(d))
      }
    }
    xhr.onerror = () => reject(new Error('Upload failed — could not reach the server.'))
    xhr.send(form)
  })
}
