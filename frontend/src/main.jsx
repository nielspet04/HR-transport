import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const nav = [['overview', 'Overzicht'], ['actions', 'Acties'], ['review', 'Maandcontrole'], ['analytics', 'Analytics'], ['employees', 'Werknemers'], ['locations', 'Locaties'], ['technical', 'Technisch beheer'], ['settings', 'Instellingen']]
const modes = ['Privé auto', 'Fiets', 'Trein', 'Dienstwagen', 'Mob budget']
const shiftModes = [['DEFAULT', 'Standaard'], ['AUTO', 'Privéauto'], ['BIKE', 'Fiets'], ['TRAIN', 'Trein'], ['COMPANY_CAR', 'Dienstwagen'], ['MOBILITY_BUDGET', 'Mobiliteitsbudget'], ['TELEWORK', 'Telework']]
const euro = value => new Intl.NumberFormat('nl-BE', { style: 'currency', currency: 'EUR' }).format(Number(value || 0))
const number = (value, maximumFractionDigits = 1) => new Intl.NumberFormat('nl-BE', { maximumFractionDigits }).format(Number(value || 0))
const kmRate = value => `€ ${String(value ?? '—').replace('.', ',')}/km`
const norm = value => String(value || '').trim().toLocaleLowerCase('nl').replace(/\s+/g, ' ')
const today = () => new Date().toISOString().slice(0, 10)
const routeVisualizationRequests = new Map()

function requestRouteVisualization(routeId, csrf) {
  if (!routeVisualizationRequests.has(routeId)) {
    routeVisualizationRequests.set(routeId, fetch(`/api/revision?csrf=${encodeURIComponent(csrf)}`)
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error('Actuele backendstatus laden mislukt.'); return body.revision })
      .then(revision => fetch('/api/action/route_visualization_request', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ revision, data: { route_id: routeId, consent: true } })
      })).then(async response => { const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.error || 'Routelijn aanvragen mislukt.') }))
  }
  return routeVisualizationRequests.get(routeId)
}

function monthLabel(value) {
  if (!value) return 'Nieuwe maand'
  const [year, month] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('nl-BE', { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1))
}

function latest(rows, predicate = () => true) {
  return rows.filter(predicate).sort((a, b) => (a.valid_from || '').localeCompare(b.valid_from || '') || (a.id || 0) - (b.id || 0)).at(-1)
}

function deriveDashboard(state, matching) {
  if (!matching) return { month: null, status: 'Nieuwe export nodig', tone: 'neutral', employees: state?.workers?.length || 0, movements: 0, sourceShifts: 0, excluded: 0, total: 0, actions: [], step: 1 }
  const monthly = matching.calculation?.monthly || {}
  const actions = []
  const coverageGroups = new Map()
  for (const issue of matching.coverage?.issues || []) coverageGroups.set(issue.reason || 'Onvolledige gegevens', (coverageGroups.get(issue.reason || 'Onvolledige gegevens') || 0) + 1)
  for (const [title, count] of coverageGroups) actions.push({ level: 'Hoog', title, count, kind: 'coverage' })
  const routeGroups = new Map()
  for (const issue of matching.route_issues || []) routeGroups.set(issue.reason || 'Route ontbreekt', (routeGroups.get(issue.reason || 'Route ontbreekt') || 0) + 1)
  for (const [title, count] of routeGroups) actions.push({ level: 'Midden', title, count, kind: 'route' })
  const calculationGroups = new Map()
  for (const employee of monthly.employees || []) for (const shift of employee.shifts || []) if (shift.status === 'BLOCKED' || shift.status === 'LATER_PHASE') calculationGroups.set(shift.reason || 'Shiftberekening geblokkeerd', (calculationGroups.get(shift.reason || 'Shiftberekening geblokkeerd') || 0) + 1)
  for (const [title, count] of calculationGroups) actions.push({ level: 'Hoog', title, count, kind: 'calculation' })
  if (matching.stale) actions.push({ level: 'Hoog', title: 'Maand gebruikt gewijzigde instellingen', count: 1, kind: 'refresh' })
  if (monthly.external_reference_missing) actions.push({ level: 'Hoog', title: 'Loonnummer ontbreekt', count: monthly.external_reference_missing, kind: 'payroll' })
  if (monthly.external_reference_changed) actions.push({ level: 'Hoog', title: 'Loonnummer wijzigde tijdens de maand', count: monthly.external_reference_changed, kind: 'payroll' })
  const automaticStatus = state.automatic_routes?.status
  const processing = ['QUEUED', 'RUNNING'].includes(automaticStatus)
    && (!monthly.ready || matching.stale || Boolean(matching.route_issues?.length))
  const ready = monthly.ready && monthly.external_references_ready && !matching.stale
  const status = processing ? 'Routes worden berekend' : actions.length || monthly.blocking ? 'Actie nodig' : ready ? 'Klaar voor Accerta-export' : 'Klaar voor controle'
  return { month: matching.month, runId: matching.run_id, status, tone: status === 'Actie nodig' ? 'warning' : ready ? 'success' : 'neutral', employees: monthly.employee_count || matching.summary?.agents || 0, movements: matching.summary?.movements || 0, sourceShifts: matching.summary?.source_shifts || 0, excluded: (monthly.excluded || 0) + (matching.summary?.ignored_shifts || 0), total: monthly.calculated_total || 0, actions, step: processing || actions.length ? 2 : ready ? 4 : 3 }
}

function Field({ label, children }) { return <label className="field">
<span>{label}</span>{children}</label> }
function AddressFields({ prefix = '', value = {} }) { return <div className="form-grid address-grid">
<Field label="Straat">
<input name={`${prefix}street`} defaultValue={value.street || ''} required />
</Field>
<Field label="Nummer">
<input name={`${prefix}number`} defaultValue={value.number || ''} required />
</Field>
<Field label="Bus">
<input name={`${prefix}unit`} defaultValue={value.unit || ''} />
</Field>
<Field label="Postcode">
<input name={`${prefix}postal_code`} defaultValue={value.postal_code || ''} required />
</Field>
<Field label="Gemeente">
<input name={`${prefix}city`} defaultValue={value.city || ''} required />
</Field>
<Field label="Landcode">
<input name={`${prefix}country`} defaultValue={value.country || 'BE'} required maxLength="2" />
</Field>
</div> }
function addressFrom(form, prefix = '') { return Object.fromEntries(['street', 'number', 'unit', 'postal_code', 'city', 'country'].map(key => [key, form.get(`${prefix}${key}`) || ''])) }
function addressLabel(address) { return address ? `${address.street} ${address.number}${address.unit ? ` bus ${address.unit}` : ''}, ${address.postal_code} ${address.city} · ${address.country}` : 'Adres ontbreekt' }

function RouteCorrection({ routeId, workerId, state, save }) {
  const route = (state.route_distances || []).find(item => item.id === routeId)
  if (!route || route.status !== 'READY') return null
  const active = (route.overrides || []).find(item => item.worker_id === workerId)
  const history = (route.correction_history || []).filter(item => item.worker_id === workerId).slice().reverse()
  const submit = (event, reset = false) => {
    event.preventDefault()
    const formElement = event.currentTarget.tagName === 'FORM' ? event.currentTarget : event.currentTarget.form
    if (!formElement.reportValidity()) return
    const form = new FormData(formElement)
    save('route_distance_override', { route_id: routeId, worker_id: workerId, ...(reset ? { reset: true } : { kms: form.get('kms') }), reason: form.get('reason') })
  }
  return <details className="route-correction">
<summary>{active ? `HR-correctie: ${active.kms} km` : 'Echte afstand corrigeren'}</summary>
<p>Mapbox blijft bewaard op <strong>{route.kms} km</strong>. Een correctie geldt alleen voor deze werknemer en wordt opgenomen in de berekening en audittrail.</p>
<form onSubmit={submit}>
<Field label="Enkele kilometers">
<input name="kms" type="number" min="0" max="100000" step="1" defaultValue={active?.kms ?? route.kms} required />
</Field>
<Field label="Reden">
<input name="reason" maxLength="500" placeholder="Waarom wijkt HR af van Mapbox?" required />
</Field>
<button className="primary">Correctie opslaan</button>{active && <button type="button" className="secondary" onClick={event => submit(event, true)}>Mapbox herstellen</button>}
</form>{history.length > 0 && <details className="correction-history">
<summary>Correctiehistoriek ({history.length})</summary>{history.map(item => <p key={item.id}>{new Date(item.changed_at).toLocaleString('nl-BE')} · {item.kms == null ? 'Mapbox hersteld' : `${item.kms} km`} · {item.reason}</p>)}</details>}
</details>
}

function Progress({ step }) { const labels = ['Export uploaden', 'Gegevens aanvullen', 'Controleren', 'Exporteren']; return <div className="progress">{labels.map((label, index) => <div className={`progress-item ${index + 1 <= step ? 'done' : ''}`} key={label}>
<span>{index + 1 < step ? '✓' : index + 1}</span>
<small>{label}</small>
</div>)}</div> }
function Stat({ label, value, detail, attention }) { return <article className="stat">
<p>{label}</p>
<strong className={attention ? 'attention' : ''}>{value}</strong>
<small>{detail}</small>
</article> }
function ActionList({ items, onResolve }) { if (!items.length) return <div className="empty">
<span>✓</span>
<strong>Geen openstaande problemen</strong>
<p>Deze maand kan zonder uitzonderingen verder.</p>
</div>; return <div className="action-list">{items.map((item, index) => <div className="action" key={`${item.title}-${index}`}>
<span className={`priority ${item.level === 'Hoog' ? 'high' : ''}`}>{item.level}</span>
<div>
<strong>{item.title}</strong>
<small>{item.count} betrokken</small>
</div>
<button className="link-button" onClick={() => onResolve?.(item)}>Oplossen →</button>
</div>)}</div> }

function MonthPicker({ state, matching, onChange }) {
  const seen = new Set()
  const runs = (state.matching_runs || []).filter(run => !seen.has(run.month) && seen.add(run.month)).sort((left, right) => right.month.localeCompare(left.month))
  const current = runs.findIndex(run => run.id === matching?.run_id)
  const newer = current > 0 ? runs[current - 1] : null
  const older = current >= 0 && current < runs.length - 1 ? runs[current + 1] : null
  return <Field label="Maand">
<div className="month-picker">
<button type="button" className="month-step" disabled={!older} onClick={() => older && onChange(older.id)} aria-label="Vorige maand">‹</button>
<select value={matching?.run_id || ''} onChange={event => onChange(Number(event.target.value))}>{runs.map(run => <option value={run.id} key={run.id}>{monthLabel(run.month)}</option>)}</select>
<button type="button" className="month-step" disabled={!newer} onClick={() => newer && onChange(newer.id)} aria-label="Volgende maand">›</button>
</div>
</Field>
}

function Overview({ data, onUpload, onExport, onResolve, busy }) {
  return <>
<header className="page-header">
<div>
<p className="eyebrow">MAANDVERWERKING</p>
<h1>{monthLabel(data.month)}</h1>
<p>Alles wat goed is verwerkt blijft uit beeld. Je ziet alleen wat aandacht nodig heeft.</p>
</div>
<span className={`status ${data.tone}`}>{data.status}</span>
</header>
<section className="panel">
<Progress step={data.step} />
</section>
<section className="stats">
<Stat label="Werknemers" value={data.employees} detail="in deze maand" />
<Stat label="Bewegingen" value={data.movements} detail={`${data.sourceShifts} bronshiften`} />
<Stat label="Problemen" value={data.actions.length} detail={data.actions.length ? 'actie vereist' : 'alles compleet'} attention={data.actions.length > 0} />
<Stat label="Totaalbedrag" value={euro(data.total)} detail={`${data.excluded} uitgesloten`} />
</section>
<section className="next-step">
<div>
<p>VOLGENDE STAP</p>
<h2>{data.status}</h2>
<span>{data.status === 'Klaar voor Accerta-export' ? 'Alle controles zijn geslaagd. De officiële export staat klaar.' : 'Werk de openstaande punten af om verder te gaan.'}</span>
</div>{data.status === 'Klaar voor Accerta-export' ? <button disabled={busy} onClick={onExport}>Accerta-export downloaden</button> : data.actions.length ? <button disabled={busy} onClick={() => onResolve(data.actions[0])}>Problemen oplossen</button> : <button disabled={busy} onClick={onUpload}>Nieuwe Pl@net-export</button>}</section>
<div className="section-title">
<h2>Aandachtspunten</h2>
</div>
<ActionList items={data.actions.slice(0, 4)} onResolve={onResolve} />
</>
}

function AgentResolution({ agent, matching, state, save }) {
  const suggested = agent.suggestions?.[0]?.worker_id || ''
  return <form className="resolution-card" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('matching_employee', { run_id: matching.run_id, planet_id: agent.planet_id, worker_id: Number(form.get('worker_id')), reason: form.get('reason') }) }}>
<div>
<span className="priority high">Hoog</span>
<h3>{agent.source_names?.join(' / ') || agent.planet_id}</h3>
<p>Deze Pl@net-agent is nog niet zeker aan een werknemer gekoppeld.</p>
</div>
<div className="form-grid">
<Field label="Bestaande werknemer">
<select name="worker_id" defaultValue={suggested} required>
<option value="">Kies werknemer…</option>{state.workers.map(worker => <option key={worker.id} value={worker.id}>{worker.name}</option>)}</select>
</Field>
<Field label="Reden">
<input name="reason" defaultValue="HR bevestigt werknemer" required />
</Field>
</div>{agent.suggestions?.length ? <p className="hint">Suggestie: {agent.suggestions.map(item => item.name).join(', ')}</p> : null}<button className="primary">Koppeling bevestigen en maand herberekenen</button>
</form>
}

function IgnoredEmployees({ state, matching, save }) {
  const ignored = (state.employee_ignores || []).filter(item => item.month === matching.month)
  if (!ignored.length) return null
  return <section className="resolution-card">
<div><span className="priority">Genegeerd</span><h3>Uitgesloten werknemers in {monthLabel(matching.month)}</h3><p>Hun shiften tellen niet mee. Een foutieve uitsluiting kan hier worden hersteld.</p></div>
{ignored.map(item => <button type="button" className="secondary" key={item.planet_id} onClick={() => save('matching_employee_restore', { run_id: matching.run_id, planet_id: item.planet_id, reason: 'Genegeerde werknemer opnieuw opnemen in maandexport' })}>Pl@net {item.planet_id} opnieuw opnemen</button>)}
</section>
}

function NewEmployeeForm({ agent, matching, state, save }) {
  const movements = matching.movements.filter(movement => movement.planet_id === agent.planet_id)
  const sources = [...new Set(movements.map(movement => movement.source_location))]
  const firstDay = movements.map(item => item.day).sort()[0]
  const monthStart = `${matching.month}-01`
  return <details className="resolution-card">
<summary>Nieuw profiel maken voor {agent.source_names?.[0]}</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('employee_onboard', { run_id: matching.run_id, planet_id: agent.planet_id, name: form.get('name'), valid_from: form.get('valid_from'), external_reference: form.get('external_reference'), address: addressFrom(form, 'home_'), assignments: sources.map((source, index) => ({ source_location: source, location: form.get(`location_${index}`), mode: form.get(`mode_${index}`) })), reason: form.get('reason') }) }}>
<div className="form-grid">
<Field label="Naam">
<input name="name" defaultValue={agent.source_names?.[0]} required />
</Field>
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={monthStart} max={firstDay} required />
</Field>
<Field label="Extern loonnummer">
<input name="external_reference" required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Nieuwe werknemer uit Pl@net bevestigd" required />
</Field>
</div>
<h4>Woonadres</h4>
<AddressFields prefix="home_" />
<h4>Werklocaties en vervoer</h4>{sources.map((source, index) => <div className="assignment" key={source}>
<strong>{source}</strong>
<select name={`location_${index}`} required>
<option value="">Kies fysieke locatie…</option>{state.physical_locations.map(location => <option key={location.key} value={location.name}>{location.name}</option>)}</select>
<select name={`mode_${index}`} defaultValue="Privé auto">{modes.map(mode => <option key={mode}>{mode}</option>)}</select>
</div>)}<div className="candidate-actions">
<button className="primary">Werknemer aanmaken</button>
<button type="button" className="secondary" onClick={() => save('matching_employee_ignore', { run_id: matching.run_id, planet_id: agent.planet_id, reason: 'Werknemer gestopt; resterende shiften in deze maandexport genegeerd' })}>Werknemer en shiften negeren</button>
</div>
</form>
</details>
}

function LocationResolution({ location, matching, state, save }) {
  const [choice, setChoice] = useState('EXISTING')
  const firstDay = matching.movements.filter(item => norm(item.source_location) === norm(location.physical_location)).map(item => item.day).sort()[0]
  return <details className="resolution-card">
<summary>Onbekende locatie: {location.physical_location}</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('customer_onboard', { run_id: matching.run_id, source_location: location.physical_location, choice, location: choice === 'EXISTING' ? form.get('existing') : form.get('new_name'), valid_from: form.get('valid_from'), address: choice === 'NEW' ? addressFrom(form, 'loc_') : undefined, reason: form.get('reason') }) }}>
<div className="form-grid">
<Field label="Behandeling">
<select name="choice" value={choice} onChange={event => setChoice(event.target.value)}>
<option value="EXISTING">Koppelen aan bestaande locatie</option>
<option value="NEW">Nieuwe fysieke locatie</option>
</select>
</Field>{choice === 'EXISTING' ? <Field label="Bestaande locatie">
<select name="existing" required>
<option value="">Kies locatie…</option>{state.physical_locations.map(item => <option key={item.key} value={item.name}>{item.name}</option>)}</select>
</Field> : <Field label="Naam nieuwe locatie">
<input name="new_name" defaultValue={location.physical_location} required />
</Field>}<Field label="Geldig vanaf">
<input type="date" name="valid_from" defaultValue={firstDay} max={firstDay} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Nieuwe klantlocatie uit Pl@net bevestigd" required />
</Field>
</div>{choice === 'NEW' && <>
<h4>Adres nieuwe locatie</h4>
<AddressFields prefix="loc_" />
</>}<button className="primary">Locatie opslaan en maand herberekenen</button>
</form>
</details>
}

function PayrollResolution({ employee, save }) {
  return <form className="resolution-card compact-form" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('external_reference_save', { worker_id: employee.worker_id, external_reference: form.get('external_reference'), valid_from: form.get('valid_from'), reason: form.get('reason') }) }}>
<div>
<span className="priority high">Hoog</span>
<h3>{employee.name}</h3>
<p>Loonnummer is {employee.external_reference_status === 'CHANGED_DURING_MONTH' ? 'gewijzigd tijdens de maand' : 'niet ingevuld'}.</p>
</div>
<Field label="Extern loonnummer">
<input name="external_reference" defaultValue={employee.external_reference || ''} required />
</Field>
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={`${employee.shifts?.[0]?.date?.slice(0, 7) || today().slice(0, 7)}-01`} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Loonnummer bevestigd door HR" required />
</Field>
<button className="primary">Opslaan</button>
</form>
}

function ActionCenter({ state, matching, data, save, onEmployee, onReview }) {
  const unresolvedAgents = (matching?.agents || []).filter(agent => agent.status !== 'MATCHED')
  const unmatchedLocations = (matching?.locations || []).filter(location => location.status === 'UNMATCHED_LOCATION')
  const payroll = (matching?.calculation?.monthly?.employees || []).filter(employee => employee.worker_id && employee.external_reference_status !== 'READY')
  const blockedShifts = (matching?.calculation?.monthly?.employees || []).flatMap(employee => (employee.shifts || []).filter(shift => shift.status === 'BLOCKED' || shift.status === 'LATER_PHASE').map(shift => ({ employee, shift })))
  return <>
<header className="simple-header">
<p className="eyebrow">CONTROLE</p>
<h1>Actielijst</h1>
<p>Los de oorzaak één keer op; daarna wordt de maand opnieuw verwerkt.</p>
</header>{matching?.stale && <div className="resolution-card inline-resolution">
<div>
<h3>Maand opnieuw berekenen</h3>
<p>Instellingen zijn gewijzigd nadat deze maand werd verwerkt.</p>
</div>
<button className="primary" onClick={() => save('matching_refresh', { run_id: matching.run_id })}>Nu herberekenen</button>
</div>}<IgnoredEmployees state={state} matching={matching} save={save} />{unresolvedAgents.map(agent => agent.status === 'UNMATCHED_EMPLOYEE' ? <NewEmployeeForm key={agent.planet_id} agent={agent} matching={matching} state={state} save={save} /> : <AgentResolution key={agent.planet_id} agent={agent} matching={matching} state={state} save={save} />)}{unmatchedLocations.map(location => <LocationResolution key={`${location.customer}-${location.physical_location}`} location={location} matching={matching} state={state} save={save} />)}{payroll.map(employee => <PayrollResolution key={employee.planet_id} employee={employee} save={save} />)}{(matching?.route_issues || []).map((issue, index) => { const worker = state.workers.find(item => item.name === issue.worker); return <div className="resolution-card inline-resolution" key={`${issue.worker}-${index}`}>
<div>
<span className="priority">Midden</span>
<h3>{issue.worker}</h3>
<p>{issue.day} · {issue.location} · {issue.reason}</p>
</div>{worker ? <button className="secondary" onClick={() => onEmployee(worker.id)}>Werknemer bekijken</button> : <span className="hint">Los eerst de agentkoppeling hierboven op.</span>}</div> })}{blockedShifts.map(({ employee, shift }) => <div className="resolution-card inline-resolution" key={`blocked-${employee.planet_id}-${shift.movement_id}`}>
<div><span className="priority high">Hoog</span><h3>{employee.name}</h3><p>{shift.date} · {shift.location} · {shift.reason}</p></div>
<button className="secondary" onClick={onReview}>Shift controleren</button>
</div>)}{!data.actions.length && <ActionList items={[]} />}</>
}

function ShiftActions({ shift, matching, locations, save }) {
  const exceptionalGap = shift.multi_location && shift.sequence > 1 && shift.gap_minutes > 120
  const employeeDefault = shift.direct_transfer_employee_default === true
  const dayButton = shift.direct_transfer_override ? (employeeDefault ? 'Alleen deze dag ontkoppelen' : 'Thuisrit herstellen') : (employeeDefault ? 'Alleen deze dag opnieuw koppelen' : 'Niet naar huis · shiften koppelen')
  return <details className="shift-actions">
<summary>Aanpassen</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('shift_transport_choice', { run_id: matching.run_id, movement_id: shift.movement_id, mode: form.get('mode'), reason: form.get('reason') }) }}>
<select name="mode" defaultValue="DEFAULT">{shiftModes.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
<input name="reason" placeholder="Reden vervoerskeuze" required />
<button className="secondary">Vervoer opslaan</button>
</form><form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('shift_location_choice', { run_id: matching.run_id, movement_id: shift.movement_id, location: form.get('location'), reason: form.get('reason') }) }}>
<select name="location" defaultValue={shift.location} required>{(locations || []).map(item => <option value={item.name} key={item.key}>{item.name}</option>)}</select>
<input name="reason" defaultValue="Foutieve shiftlocatie in Pl@net gecorrigeerd door HR" required />
<button className="secondary">Shiftlocatie aanpassen</button>
</form>{shift.location_corrected && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('shift_location_choice', { run_id: matching.run_id, movement_id: shift.movement_id, reset: true, reason: form.get('reason') }) }}>
<input name="reason" defaultValue="Locatiecorrectie verwijderd; oorspronkelijke Pl@net-locatie herstellen" required />
<button className="secondary">Oorspronkelijke locatie herstellen</button>
</form>}{shift.status === 'CALCULATED' && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('calculation_amount_correction', { run_id: matching.run_id, movement_id: shift.movement_id, amount: form.get('amount'), reason: form.get('reason') }) }}>
<input name="amount" inputMode="decimal" defaultValue={shift.amount} required />
<input name="reason" placeholder="Reden bedragscorrectie" required />
<button className="secondary">Bedrag corrigeren</button>
</form>}{exceptionalGap && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('itinerary_transfer_override', { run_id: matching.run_id, movement_id: shift.movement_id, direct_transfer: !shift.direct_transfer_override, reason: form.get('reason') }) }}>
<input name="reason" defaultValue={shift.direct_transfer_override ? (employeeDefault ? 'Uitzondering: werknemer ging deze dag wel naar huis tussen beide shiften' : 'HR herstelt thuisrit tussen beide shiften') : 'HR bevestigt dat de agent niet naar huis ging tussen beide shiften'} required />
<button className="secondary">{dayButton}</button>
</form>}{exceptionalGap && !employeeDefault && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('itinerary_employee_default', { run_id: matching.run_id, movement_id: shift.movement_id, direct_transfer: true, reason: form.get('reason') }) }}>
<input name="reason" defaultValue="HR bevestigt dat deze werknemer bij meerdere shiften standaard niet naar huis gaat" required />
<button className="secondary">Altijd koppelen voor deze werknemer</button>
</form>}{exceptionalGap && employeeDefault && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('itinerary_employee_default', { run_id: matching.run_id, movement_id: shift.movement_id, direct_transfer: false, reason: form.get('reason') }) }}>
<input name="reason" defaultValue="HR verwijdert de vaste koppeling; gewone twee-uursregel opnieuw toepassen" required />
<button className="secondary">Vaste koppeling verwijderen</button>
</form>}</details>
}

const statusLabels = { CALCULATED: 'Berekend', BLOCKED: 'Geblokkeerd', LATER_PHASE: 'Later verwerken', EXCLUDED_TRAIN: 'Trein uitgesloten', EXCLUDED_COMPANY_CAR: 'Dienstwagen uitgesloten', EXCLUDED_MOBILITY_BUDGET: 'Mobiliteitsbudget uitgesloten', EXCLUDED_TELEWORK: 'Telewerk', EXCLUDED_SAME_LOCATION: 'Zelfde locatie · geen extra rit' }
const shiftTypeLabels = { STANDARD: 'Gewone auto', SPECIAL: 'Vroeg/laat', EXTRA48: '48u-oproep', BICYCLE: 'Fiets', TRAIN: 'Trein', COMPANY_CAR: 'Dienstwagen', MOBILITY_BUDGET: 'Mobiliteitsbudget', TELEWORK: 'Telewerk', UNRESOLVED: 'Nog te bepalen' }
function shiftType(shift) {
  if (shift.extra_shift_48h) return 'EXTRA48'
  if (shift.early_late) return 'SPECIAL'
  if (shift.tariff_kind) return shift.tariff_kind
  return ({ EXCLUDED_TRAIN: 'TRAIN', EXCLUDED_COMPANY_CAR: 'COMPANY_CAR', EXCLUDED_MOBILITY_BUDGET: 'MOBILITY_BUDGET', EXCLUDED_TELEWORK: 'TELEWORK' })[shift.status] || 'UNRESOLVED'
}
const shortDate = value => new Intl.DateTimeFormat('nl-BE', { weekday: 'short', day: '2-digit', month: 'short' }).format(new Date(`${value}T12:00:00`))

function CalculationDetails({ shift }) {
  const source = shift.source_shifts || []
  return <div className="calculation-details">
<div className="calculation-story">
<span>Berekening</span>
<strong>{shift.rule || 'Geen bedrag berekend'}</strong>
<p>{shift.reason || 'Geen aanvullende uitleg beschikbaar.'}</p>
</div>
<dl>
<div>
<dt>Bedrag</dt>
<dd>{shift.amount == null ? 'Niet van toepassing' : euro(shift.amount)}{shift.amount_source === 'HR' ? ' · HR-correctie' : ''}</dd>
</div>
<div>
<dt>Vergoede afstand</dt>
<dd>{shift.reimbursed_kms ? `${shift.reimbursed_kms} km` : shift.distance ? `${shift.distance} km enkele rit` : 'Niet van toepassing'}</dd>
</div>
<div>
<dt>Afstandsbron</dt>
<dd>{shift.distance_source || '—'}{shift.distance_valid_from ? ` · geldig vanaf ${shift.distance_valid_from}` : ''}</dd>
</div>
<div>
<dt>Tarief</dt>
<dd>{shift.rate_per_km ? `${euro(shift.rate_per_km)}/km` : shift.tariff_kind || '—'}</dd>
</div>
<div>
<dt>Tariefbron</dt>
<dd>{shift.tariff_source || '—'}{shift.tariff_valid_from ? ` · ${shift.tariff_valid_from}` : ''}</dd>
</div>
<div>
<dt>Bronshift</dt>
<dd>{source.length ? source.map(item => `${item.start}–${item.end} · ${item.customer}`).join(' / ') : `Beweging #${shift.movement_id}`}</dd>
</div>{shift.original_amount && <div>
<dt>Oorspronkelijk</dt>
<dd>{euro(shift.original_amount)} · {shift.amount_override_reason}</dd>
</div>}{shift.override_reason && <div>
<dt>Vervoerskeuze</dt>
<dd>{shift.override_reason}</dd>
</div>}{shift.multi_location && shift.sequence > 1 && <div>
<dt>Dagroute</dt>
<dd>{shift.origin_location ? `${shift.origin_location} → ${shift.location}` : `Thuis → ${shift.location}`} · pauze {Math.floor((shift.gap_minutes || 0) / 60)}u{String((shift.gap_minutes || 0) % 60).padStart(2, '0')}{shift.direct_transfer_override ? ' · bevestigd: agent ging niet naar huis' : ''}</dd>
</div>}{shift.location_corrected && <div>
<dt>Locatiecorrectie</dt>
<dd>Pl@net: {shift.original_location} → HR: {shift.location} · {shift.location_correction_reason}</dd>
</div>}</dl>
</div>
}

function EmployeeCalendar({ month, shifts, selectedMovement, selectedDate, onSelect, onClear }) {
  const [year, monthNumber] = month.split('-').map(Number)
  const daysInMonth = new Date(year, monthNumber, 0).getDate()
  const mondayOffset = (new Date(year, monthNumber - 1, 1).getDay() + 6) % 7
  const byDay = new Map()
  for (const shift of shifts) {
    const day = Number(shift.date.slice(-2))
    if (!byDay.has(day)) byDay.set(day, [])
    byDay.get(day).push(shift)
  }
  function choose(day) {
    const entries = byDay.get(day) || []
    if (entries.length) onSelect(entries)
  }
  return <section className="employee-calendar" aria-label={`Shiftkalender ${monthLabel(month)}`}>
<div className="calendar-title">
<div>
<strong>Shiftkalender</strong>
<span>{monthLabel(month)}</span>
</div>{selectedMovement || selectedDate ? <button type="button" onClick={onClear}>Alle shiften</button> : <small>
<i /> Shift aanwezig</small>}</div>
<div className="calendar-weekdays">{['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo'].map(day => <span key={day}>{day}</span>)}</div>
<div className="calendar-days">{Array.from({ length: mondayOffset }, (_, index) => <span className="calendar-empty" key={`empty-${index}`} />)}{Array.from({ length: daysInMonth }, (_, index) => { const day = index + 1; const entries = byDay.get(day) || []; const hasProblem = entries.some(shift => shift.status === 'BLOCKED' || shift.status === 'LATER_PHASE'); const selected = entries.some(shift => shift.movement_id === selectedMovement || shift.date === selectedDate); return <button type="button" key={day} disabled={!entries.length} className={`${entries.length ? 'has-shift' : ''} ${hasProblem ? 'has-problem' : ''} ${selected ? 'selected' : ''}`} onClick={() => choose(day)} aria-label={entries.length ? `${day}: ${entries.length} shift${entries.length === 1 ? '' : 'en'}` : `${day}: geen shift`}>
<span>{day}</span>{entries.length > 1 && <b>{entries.length}</b>}</button> })}</div>
</section>
}

function MonthReview({ matching, state, save }) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('ALL')
  const [kind, setKind] = useState('ALL')
  const [status, setStatus] = useState('ALL')
  const [location, setLocation] = useState('ALL')
  const [expanded, setExpanded] = useState(null)
  const [focusedMovement, setFocusedMovement] = useState(null)
  const [focusedDate, setFocusedDate] = useState(null)
  const [focusedAgent, setFocusedAgent] = useState(null)
  const allEmployees = matching?.calculation?.monthly?.employees || []
  const allShifts = allEmployees.flatMap(employee => employee.shifts)
  const modesAvailable = [...new Set(allShifts.map(shift => shift.mode || 'Niet ingesteld'))].sort()
  const kindsAvailable = [...new Set(allShifts.map(shiftType))].sort((a, b) => Object.keys(shiftTypeLabels).indexOf(a) - Object.keys(shiftTypeLabels).indexOf(b))
  const statusesAvailable = [...new Set(allShifts.map(shift => shift.status))].sort()
  const locationsAvailable = [...new Set(allShifts.map(shift => shift.location))].sort()
  const employees = allEmployees.map(employee => { const filteredShifts = employee.shifts.filter(shift => (mode === 'ALL' || (shift.mode || 'Niet ingesteld') === mode) && (kind === 'ALL' || shiftType(shift) === kind) && (status === 'ALL' || shift.status === status) && (location === 'ALL' || shift.location === location)); const belongsToFocus = !focusedAgent || employee.planet_id === focusedAgent; return { ...employee, calendarShifts: filteredShifts, shifts: !belongsToFocus ? [] : focusedMovement ? filteredShifts.filter(shift => shift.movement_id === focusedMovement) : focusedDate ? filteredShifts.filter(shift => shift.date === focusedDate) : filteredShifts } }).filter(employee => employee.name.toLowerCase().includes(query.toLowerCase()) && employee.shifts.length)
  const shownShifts = employees.reduce((count, employee) => count + employee.shifts.length, 0)
  const shownTotal = employees.flatMap(employee => employee.shifts).reduce((sum, shift) => sum + (shift.status === 'CALCULATED' ? Number(shift.amount || 0) : 0), 0)
  const clearFocus = () => { setFocusedMovement(null); setFocusedDate(null); setFocusedAgent(null); setExpanded(null) }
  const focusShift = (planetId, shift) => { setFocusedAgent(planetId); setFocusedDate(null); setFocusedMovement(shift.movement_id); setExpanded(shift.movement_id); requestAnimationFrame(() => document.getElementById(`shift-${shift.movement_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })) }
  const focusDay = (planetId, shifts) => { setFocusedAgent(planetId); setFocusedMovement(null); setFocusedDate(shifts[0].date); setExpanded(null); requestAnimationFrame(() => document.getElementById(`shift-${shifts[0].movement_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })) }
  const clearFilters = () => { setQuery(''); setMode('ALL'); setKind('ALL'); setStatus('ALL'); setLocation('ALL'); clearFocus() }
  return <>
<header className="simple-header review-header">
<div>
<p className="eyebrow">MAANDCONTROLE</p>
<h1>{monthLabel(matching?.month)}</h1>
<p>Bekijk per shift hoe het bedrag tot stand kwam en filter op wat je wilt controleren.</p>
</div>
<div className="review-totals">
<div>
<strong>{shownShifts}</strong>
<span>shiften zichtbaar</span>
</div>
<div>
<strong>{euro(shownTotal)}</strong>
<span>zichtbaar totaal</span>
</div>
</div>
</header>
<section className="review-filters">
<Field label="Zoek werknemer">
<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Naam…" />
</Field>
<Field label="Vervoersmiddel">
<select value={mode} onChange={event => setMode(event.target.value)}>
<option value="ALL">Alle vervoersmiddelen</option>{modesAvailable.map(item => <option key={item}>{item}</option>)}</select>
</Field>
<Field label="Shiftsoort">
<select value={kind} onChange={event => setKind(event.target.value)}>
<option value="ALL">Alle shiftsoorten</option>{kindsAvailable.map(item => <option value={item} key={item}>{shiftTypeLabels[item] || item}</option>)}</select>
</Field>
<Field label="Status">
<select value={status} onChange={event => setStatus(event.target.value)}>
<option value="ALL">Alle statussen</option>{statusesAvailable.map(item => <option value={item} key={item}>{statusLabels[item] || item}</option>)}</select>
</Field>
<Field label="Locatie">
<select value={location} onChange={event => setLocation(event.target.value)}>
<option value="ALL">Alle locaties</option>{locationsAvailable.map(item => <option key={item}>{item}</option>)}</select>
</Field>
<button className="filter-reset" onClick={clearFilters}>Filters wissen</button>
</section>{employees.length ? <div className="review-list">{employees.map(employee => { const filteredTotal = employee.shifts.reduce((sum, shift) => sum + (shift.status === 'CALCULATED' ? Number(shift.amount || 0) : 0), 0); return <details className={employee.blocking ? 'review-worker blocked' : 'review-worker'} key={employee.planet_id}>
<summary>
<span className="employee-summary">
<strong>{employee.name}</strong>
<small>{employee.external_reference || 'Loonnummer ontbreekt'}</small>
</span>
<span>{employee.shifts.length} shiften</span>
<b>{euro(filteredTotal)}</b>
<i>{employee.blocking ? `${employee.blocking} blokkering` : 'Gereed'}</i>
</summary>
<EmployeeCalendar month={matching.month} shifts={employee.calendarShifts} selectedMovement={focusedMovement} selectedDate={focusedDate} onSelect={shifts => focusDay(employee.planet_id, shifts)} onClear={clearFocus} />
<div className="shift-list">
<div className="shift-list-head">
<span>Datum</span>
<span>Locatie</span>
<span>Vervoer</span>
<span>Status</span>
<span>Afstand</span>
<span>Bedrag</span>
<span />
</div>{employee.shifts.map(shift => <article id={`shift-${shift.movement_id}`} className={`shift-row ${expanded === shift.movement_id ? 'open' : ''}`} key={shift.movement_id} onClick={() => focusShift(employee.planet_id, shift)}>
<div className="shift-main">
<span className="shift-date">
<strong>{shortDate(shift.date)}</strong>
<small>{shift.date}</small>
</span>
<span className="shift-location"><strong>{shift.location}</strong>{shift.location_corrected && <small>Pl@net: {shift.original_location}</small>}</span>
<span className="mode-pill with-kind">{shift.mode || 'Niet ingesteld'}<small>{shiftTypeLabels[shiftType(shift)]}</small></span>
<span className={`status-pill ${shift.status === 'CALCULATED' ? 'ok' : shift.status.startsWith('EXCLUDED_') ? 'excluded' : 'problem'}`}>{statusLabels[shift.status] || shift.status}</span>
<span>{shift.distance == null ? '—' : `${shift.distance} km`}</span>
<strong>{shift.amount == null ? '—' : euro(shift.amount)}</strong>
<button className="details-button" aria-expanded={expanded === shift.movement_id} onClick={event => { event.stopPropagation(); setExpanded(expanded === shift.movement_id ? null : shift.movement_id) }}>{expanded === shift.movement_id ? 'Sluiten' : 'Berekening'}</button>
</div>{(expanded === shift.movement_id || focusedDate === shift.date) && <div className="shift-detail-panel">
<CalculationDetails shift={shift} />
<ShiftActions shift={shift} matching={matching} locations={state.physical_locations} save={save} />
</div>}</article>)}</div>
</details> })}</div> : <div className="empty">
<span>⌕</span>
<strong>Geen shiften gevonden</strong>
<p>Pas de filters aan om andere resultaten te zien.</p>
<button className="secondary" onClick={clearFilters}>Alle filters wissen</button>
</div>}</>
}

function AnalyticsBar({ label, value, maximum, detail, rank }) {
  const width = maximum ? Math.max(3, Number(value) / maximum * 100) : 0
  return <div className="analytics-bar-row">
<span className="analytics-rank">{rank || ''}</span>
<div className="analytics-bar-copy"><strong>{label}</strong><small>{detail}</small></div>
<div className="analytics-bar-track" aria-hidden="true"><i style={{ width: `${width}%` }} /></div>
<b>{euro(value)}</b>
</div>
}

function Analytics({ analytics, month, loading, error }) {
  const [trendMetric, setTrendMetric] = useState('cost')
  if (loading && !analytics) return <div className="analytics-loading"><div className="loader" /><strong>Analytics worden berekend…</strong><span>Alle geïmporteerde maanden worden samengevat.</span></div>
  if (error && !analytics) return <div className="empty"><span>!</span><strong>Analytics konden niet worden geladen</strong><p>{error}</p></div>
  const months = analytics?.months || []
  const selected = months.find(item => item.month === month) || months.at(-1)
  if (!selected) return <><header className="simple-header"><p className="eyebrow">ANALYTICS</p><h1>Vervoersanalyse</h1><p>Importeer eerst een maand om kosten en kilometers te analyseren.</p></header><div className="empty"><span>↗</span><strong>Nog geen maandgegevens</strong></div></>
  const employees = (analytics.employees_by_month?.[selected.month] || []).slice(0, 10)
  const customers = analytics.customers_by_month?.[selected.month] || []
  const maxEmployee = Math.max(...employees.map(item => Number(item.cost)), 0)
  const trendValues = months.map(item => Number(item[trendMetric] || 0))
  const trendMaximum = Math.max(...trendValues, 1)
  const trendPoints = months.map((item, index) => {
    const x = months.length === 1 ? 360 : 42 + index * (636 / (months.length - 1))
    const y = 190 - (Number(item[trendMetric] || 0) / trendMaximum * 145)
    return { item, x, y }
  })
  return <>
<header className="simple-header analytics-header">
<p className="eyebrow">ANALYTICS · {monthLabel(selected.month).toUpperCase()}</p>
<h1>Vervoersanalyse</h1>
<p>Kosten, vergoede kilometers en uren op basis van dezelfde gecontroleerde berekeningen als de maandcontrole.</p>
</header>
<section className="analytics-kpis">
<article><span>Totaal vergoede km</span><strong>{number(selected.kms)} km</strong><small>{selected.shifts} berekende shiften</small></article>
<article><span>Totale kost</span><strong>{euro(selected.cost)}</strong><small>{selected.employee_count} werknemers met vergoeding</small></article>
<article><span>Gem. km / werknemer / shift</span><strong>{number(selected.average_employee_kms)} km</strong><small>Eerst per werknemer, daarna gemiddeld</small></article>
<article><span>Gem. kost / werknemer / shift</span><strong>{euro(selected.average_employee_cost)}</strong><small>{euro(selected.average_hour_cost)} gemiddeld per uur</small></article>
</section>
<section className="analytics-grid">
<article className="analytics-panel analytics-trend">
<div className="analytics-panel-head"><div><p className="eyebrow">MAANDTREND</p><h2>Alle opgeslagen maanden</h2></div><span>{months.length} maanden</span></div>
<div className="trend-switch" aria-label="Trendmetriek"><button className={trendMetric === 'cost' ? 'active' : ''} onClick={() => setTrendMetric('cost')}>Kosten</button><button className={trendMetric === 'kms' ? 'active' : ''} onClick={() => setTrendMetric('kms')}>Kilometers</button></div>
<div className="trend-chart" role="img" aria-label={`${trendMetric === 'cost' ? 'Kosten' : 'Kilometers'} per opgeslagen maand`}>
<svg viewBox="0 0 720 230" preserveAspectRatio="none" aria-hidden="true">
<line x1="42" y1="45" x2="678" y2="45" /><line x1="42" y1="117.5" x2="678" y2="117.5" /><line x1="42" y1="190" x2="678" y2="190" />
<polyline points={trendPoints.map(point => `${point.x},${point.y}`).join(' ')} />
{trendPoints.map(point => <g key={point.item.month}><circle className={point.item.month === selected.month ? 'selected' : ''} cx={point.x} cy={point.y} r="5" /><text className="trend-value" x={point.x} y={Math.max(point.y - 12, 18)} textAnchor="middle">{trendMetric === 'cost' ? euro(point.item.cost).replace(/\s/g, '') : `${number(point.item.kms)} km`}</text><text className="trend-label" x={point.x} y="215" textAnchor="middle">{point.item.month.slice(5)}/{point.item.month.slice(2, 4)}</text></g>)}
</svg>
</div>
<div className="trend-summary"><span><i />{trendMetric === 'cost' ? 'Totale kost' : 'Vergoede kilometers'}</span><strong>{trendMetric === 'cost' ? euro(selected.cost) : `${number(selected.kms)} km`} · {monthLabel(selected.month)}</strong></div>
</article>
<article className="analytics-panel analytics-averages">
<div className="analytics-panel-head"><div><p className="eyebrow">WERKNEMERSNIVEAU</p><h2>Gemiddelde kost</h2></div></div>
<div className="average-feature"><span>Per berekende shift</span><strong>{euro(selected.average_shift_cost)}</strong></div>
<div className="average-feature"><span>Per gepresteerd uur</span><strong>{selected.average_hour_cost == null ? '—' : euro(selected.average_hour_cost)}</strong></div>
<p>Uren komen uit de begin- en einduren van de bronshiften. Uitgesloten en geblokkeerde shiften tellen niet mee.</p>
</article>
</section>
<section className="analytics-panel employee-ranking">
<div className="analytics-panel-head"><div><p className="eyebrow">WERKNEMERSNIVEAU</p><h2>Top 10 werknemers · maandkost</h2></div><span>{monthLabel(selected.month)}</span></div>
{employees.length ? <div>{employees.map((item, index) => <AnalyticsBar key={`${item.worker_id}-${item.name}`} rank={index + 1} label={item.name} value={item.cost} maximum={maxEmployee} detail={`${number(item.kms)} km · ${item.shifts} shiften · ${item.average_hour_cost == null ? 'geen uren' : `${euro(item.average_hour_cost)}/uur`}`} />)}</div> : <div className="empty compact"><strong>Geen berekende werknemerskosten</strong></div>}
</section>
<section className="analytics-panel customer-analytics">
<div className="analytics-panel-head"><div><p className="eyebrow">KLANTNIVEAU</p><h2>Kilometers en kosten per klant</h2></div><span>{customers.length} klanten</span></div>
<div className="analytics-table-wrap"><table><thead><tr><th>Klant</th><th>Vergoede km</th><th>Totale kost</th><th>Uren</th><th>Kost / uur</th></tr></thead><tbody>{customers.map(item => <tr key={item.customer}><td><strong>{item.customer}</strong></td><td>{number(item.kms)} km</td><td><strong>{euro(item.cost)}</strong></td><td>{number(item.hours)} u</td><td>{item.cost_per_hour == null ? '—' : euro(item.cost_per_hour)}</td></tr>)}</tbody></table></div>
<div className="customer-analytics-cards">{customers.map(item => <article key={item.customer}>
<h3>{item.customer}</h3>
<div><span>Vergoede kilometers</span><strong>{number(item.kms)} km</strong></div>
<div><span>Totale kost</span><strong>{euro(item.cost)}</strong></div>
<small>{number(item.hours)} gepresteerde uren · {item.cost_per_hour == null ? 'geen uurkost' : `${euro(item.cost_per_hour)} per uur`}</small>
</article>)}</div>
{!customers.length && <div className="empty compact"><strong>Geen berekende klantkosten</strong></div>}
</section>
<p className="analytics-method">{analytics.method}</p>
</>
}

function RouteMapModalDiagram({ route, csrf, onClose }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    fetch(`/api/routing/preview?id=${route.route_id}&csrf=${encodeURIComponent(csrf)}`)
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Routekaart laden mislukt.'); return body })
      .then(body => active && setPreview(body))
      .catch(reason => active && setError(reason.message))
    return () => { active = false }
  }, [route.route_id, csrf])
  const line = preview?.points?.map(point => point.join(',')).join(' ') || ''
  const first = preview?.points?.[0], last = preview?.points?.at(-1)
  return <div className="modal-backdrop route-map-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
<section className="route-map-modal" role="dialog" aria-modal="true" aria-label={`Routekaart naar ${route.location}`}>
<button className="close" onClick={onClose}>×</button>
<p className="eyebrow">ROUTEVERANTWOORDING</p>
<h2>{route.worker_name ? `${route.worker_name} → ` : ''}{route.location}</h2>
<div className="route-map-meta">
<span>
<small>Vervoer</small>
<strong>{route.mode}</strong>
</span>
<span>
<small>Mapbox-afstand</small>
<strong>{route.kms} km</strong>
</span>{route.configured_kms != null && <span>
<small>Gebruikte afstand</small>
<strong>{route.configured_kms} km</strong>
</span>}</div>{error ? <div className="route-map-empty">
<strong>Kaart kon niet worden geladen</strong>
<p>{error}</p>
</div> : !preview ? <div className="route-map-loading">
<div className="loader" />
<span>Opgeslagen routelijn laden…</span>
</div> : preview.status !== 'READY' ? <div className="route-map-empty">
<strong>Routelijn nog niet opgeslagen</strong>
<p>Deze oude afstand heeft nog geen kaartlijn. Vraag die eenmalig aan via Technisch beheer; hier gebeurt nooit automatisch een Mapbox-aanvraag.</p>
</div> : <div className="route-canvas">
<svg viewBox="0 0 900 600" role="img" aria-label={`Opgeslagen route van startpunt naar ${route.location}`}>
<defs>
<pattern id="map-grid" width="72" height="72" patternUnits="userSpaceOnUse">
<path d="M72 0H0V72" fill="none" stroke="#dfe8e3" strokeWidth="1" />
</pattern>
<filter id="route-shadow">
<feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity=".18" />
</filter>
</defs>
<rect width="900" height="600" fill="#f1f5f2" />
<rect width="900" height="600" fill="url(#map-grid)" />
<path d="M-30 470 C190 350 260 520 520 360 S760 200 940 260" fill="none" stroke="#fff" strokeWidth="24" opacity=".8" />
<path d="M80 40 C200 160 330 120 430 230 S650 460 850 500" fill="none" stroke="#e5ece8" strokeWidth="14" />
<polyline points={line} fill="none" stroke="#fff" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round" filter="url(#route-shadow)" />
<polyline points={line} fill="none" stroke="#c51230" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />{first && <>
<circle cx={first[0]} cy={first[1]} r="13" fill="#fff" />
<circle cx={first[0]} cy={first[1]} r="8" fill="#003468" />
</>}{last && <>
<circle cx={last[0]} cy={last[1]} r="13" fill="#fff" />
<circle cx={last[0]} cy={last[1]} r="8" fill="#c1661d" />
</>}</svg>
<div className="route-legend">
<span>
<i className="start" /> Start</span>
<span>
<i className="finish" /> Bestemming</span>
</div>
</div>}<div className="route-map-note">
<strong>Geen verbruik bij bekijken</strong>
<p>Deze kaart tekent uitsluitend de permanent opgeslagen Mapbox-routelijn. Openen, sluiten en opnieuw bekijken veroorzaakt 0 nieuwe Mapbox API-aanvragen.</p>
</div>
</section>
</div>
}

function RouteMapModal({ route, csrf, onClose }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [backgroundError, setBackgroundError] = useState(false)
  useEffect(() => {
    let active = true
    const previewUrl = `/api/routing/preview?id=${route.route_id}&csrf=${encodeURIComponent(csrf)}`
    const loadPreview = () => fetch(previewUrl).then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Routekaart laden mislukt.'); return body })
    loadPreview()
      .then(async body => {
        if (body.status !== 'MISSING') return body
        if (active) setPreview({ status: 'REQUESTING' })
        await requestRouteVisualization(route.route_id, csrf)
        return loadPreview()
      })
      .then(body => active && setPreview(body))
      .catch(reason => active && setError(reason.message))
    return () => { active = false }
  }, [route.route_id, csrf])
  const points = preview?.points || []
  const line = points.map(point => point.join(',')).join(' ')
  const first = points[0], last = points.at(-1)
  const backgroundUrl = `/api/routing/map-background?id=${route.route_id}&csrf=${encodeURIComponent(csrf)}`
  return <div className="modal-backdrop route-map-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
    <section className="route-map-modal" role="dialog" aria-modal="true" aria-label={`Routekaart naar ${route.location}`}>
      <button className="close" onClick={onClose}>×</button>
      <p className="eyebrow">ROUTEVERANTWOORDING</p>
      <h2>{route.worker_name ? `${route.worker_name} → ` : ''}{route.location}</h2>
      <div className="route-map-meta">
<span>
<small>Vervoer</small>
<strong>{route.mode}</strong>
</span>
<span>
<small>Mapbox-afstand</small>
<strong>{route.kms} km</strong>
</span>{route.configured_kms != null && <span>
<small>Gebruikte afstand</small>
<strong>{route.configured_kms} km</strong>
</span>}</div>
      {error ? <div className="route-map-empty">
<strong>Kaart kon niet worden geladen</strong>
<p>{error}</p>
</div>
        : !preview ? <div className="route-map-loading">
<div className="loader" />
<span>Opgeslagen routelijn laden…</span>
</div>
        : preview.status === 'REQUESTING' || preview.status === 'PENDING' ? <div className="route-map-loading">
<div className="loader" />
<strong>Routelijn éénmalig aanvragen…</strong>
<span>De bestaande kilometerafstand blijft ongewijzigd.</span>
</div>
        : preview.status !== 'READY' ? <div className="route-map-empty">
<strong>Routelijn niet beschikbaar</strong>
<p>{preview.message || 'De eenmalige Mapbox-aanvraag kon niet worden voltooid.'}</p>
</div>
        : <div className="route-canvas real-route-canvas">
          {!backgroundError && <img src={backgroundUrl} onError={() => setBackgroundError(true)} alt="Mapbox-stratenkaart van de route" />}
          <svg viewBox="0 0 900 600" role="img" aria-label={`Route van startpunt naar ${route.location}`}>
            <filter id="real-route-shadow">
<feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity=".3" />
</filter>
            <polyline points={line} fill="none" stroke="#fff" strokeWidth="13" strokeLinecap="round" strokeLinejoin="round" filter="url(#real-route-shadow)" />
            <polyline points={line} fill="none" stroke="#c51230" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
            {first && <>
<circle cx={first[0]} cy={first[1]} r="14" fill="#fff" />
<circle cx={first[0]} cy={first[1]} r="8" fill="#003468" />
</>}
            {last && <>
<circle cx={last[0]} cy={last[1]} r="14" fill="#fff" />
<circle cx={last[0]} cy={last[1]} r="8" fill="#c1661d" />
</>}
          </svg>
          <div className="route-legend">
<span>
<i className="start" /> Start</span>
<span>
<i className="finish" /> Bestemming</span>
</div>
          {backgroundError && <div className="map-background-error">Stratenkaart niet beschikbaar; controleer de Mapbox-token.</div>}
        </div>}
      <div className="route-map-note">
<strong>Echte Mapbox-stratenkaart</strong>
<p>De groene lijn is de exact opgeslagen route waarmee de kilometers berekend zijn. De kaartachtergrond wordt maximaal één keer per cacheperiode opgehaald en het maandverbruik is hard begrensd.</p>
</div>
    </section>
  </div>
}

function WorkerDialogBase({ workerId, state, onClose, save, children }) {
  const worker = state.workers.find(item => item.id === workerId)
  if (!worker) return null
  const address = latest(state.addresses || [], item => item.worker_id === workerId)
  const reference = latest(state.external_references || [], item => item.worker_id === workerId)
  const routes = state.routes.filter(route => route.worker_id === workerId)
  const routeGroups = [...routes.reduce((groups, route) => {
    if (!groups.has(route.location_key)) groups.set(route.location_key, [])
    groups.get(route.location_key).push(route)
    return groups
  }, new Map()).values()]
  const selectedMonthStart = state.matching?.month ? `${state.matching.month}-01` : today()
  const selectedMonthEnd = state.matching?.month ? `${state.matching.month}-31` : '9999-12-31'
  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
<section className="modal">
<button className="close" onClick={onClose}>×</button>
<p className="eyebrow">WERKNEMERSPROFIEL</p>
<h2>{worker.name}</h2>
<div className="profile-summary">
<div>
<small>Loonnummer</small>
<strong>{reference?.external_reference || 'Ontbreekt'}</strong>
</div>
<div>
<small>Woonadres</small>
<strong>{addressLabel(address?.address)}</strong>
</div>
<div>
<small>Werklocaties</small>
<strong>{routeGroups.length}</strong>
</div>
</div>
<h3>Vervoer en afstanden</h3>
<div className="route-list">{routeGroups.map(group => { const route = group[0]; const transport = latest(state.transport_defaults || [], item => item.worker_id === workerId && item.location_key === route.location_key && item.valid_from <= selectedMonthEnd); const routeModes = [...new Set(group.map(item => item.mode))]; const selectedMode = transport?.mode || (routeModes.length === 1 ? routeModes[0] : ''); return <details key={route.location_key}>
<summary>
<strong>{route.location}</strong>
<span>{transport ? `Standaard: ${transport.mode} · vanaf ${transport.valid_from}` : routeModes.length === 1 ? `Vervoer: ${routeModes[0]}` : 'Standaard nog niet gekozen'}</span>
<b>{routeModes.join(' / ')}</b>
</summary>
<form className="form-grid" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('transport_default', { worker_id: workerId, location: route.location, mode: form.get('mode'), valid_from: form.get('valid_from'), reason: form.get('reason') }) }}>
<Field label="Standaard vervoer">
<select key={`transport-${transport?.id || 'nieuw'}-${selectedMode}`} name="mode" defaultValue={selectedMode} required>
{!selectedMode && <option value="" disabled>Kies standaard vervoer…</option>}{modes.map(mode => <option key={mode}>{mode}</option>)}</select>
</Field>
<Field label="Geldig vanaf">
<input key={`transport-date-${transport?.id || 'nieuw'}`} name="valid_from" type="date" defaultValue={transport?.valid_from || selectedMonthStart} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Vervoer aangepast door HR" required />
</Field>
<button className="secondary">Vervoer opslaan</button>
</form>{group.filter(item => item.km_applicable).map(distanceRoute => { const version = latest(state.versions || [], item => item.route_id === distanceRoute.id); return <form className="form-grid" key={distanceRoute.id} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('route_update', { route_id: distanceRoute.id, kms: form.get('kms'), valid_from: form.get('valid_from'), reason: form.get('reason') }) }}>
<Field label="Kilometers">
<input name="kms" inputMode="decimal" defaultValue={version?.kms || ''} required />
</Field>
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={today()} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Afstand aangepast door HR" required />
</Field>
<button className="secondary">Afstand {distanceRoute.mode} opslaan</button>
</form>})}</details>})}</div>
<div className="profile-forms">
<details>
<summary>Naam aanpassen</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('worker_rename', { worker_id: workerId, name: form.get('name') }) }}>
<Field label="Naam">
<input name="name" defaultValue={worker.name} required />
</Field>
<button className="secondary">Opslaan</button>
</form>
</details>
<details>
<summary>Loonnummer toevoegen of wijzigen</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('external_reference_save', { worker_id: workerId, external_reference: form.get('external_reference'), valid_from: form.get('valid_from'), reason: form.get('reason') }) }}>
<div className="form-grid">
<Field label="Loonnummer">
<input name="external_reference" defaultValue={reference?.external_reference || ''} required />
</Field>
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={today()} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Loonnummer aangepast door HR" required />
</Field>
</div>
<button className="secondary">Opslaan</button>
</form>
</details>
<details>
<summary>Woonadres toevoegen of wijzigen</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('address_save', { worker_id: workerId, valid_from: form.get('valid_from'), address: addressFrom(form, 'worker_'), reason: form.get('reason') }) }}>
<AddressFields prefix="worker_" />
<div className="form-grid">
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={today()} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Woonadres aangepast door HR" required />
</Field>
</div>
<button className="secondary">Opslaan</button>
</form>
</details>
</div>
{children}
</section>
</div>
}

function WorkerDialog({ workerId, state, onClose, save }) {
  const [selectedMap, setSelectedMap] = useState(null)
  const worker = state.workers.find(item => item.id === workerId)
  const routes = state.routes.filter(route => route.worker_id === workerId)
  const maps = (state.route_maps || []).filter(route => route.worker_id === workerId)
  return <>
<WorkerDialogBase workerId={workerId} state={state} onClose={onClose} save={save}>
<section className="route-map-dock" aria-label="Routekaarten werknemer">
<div>
<strong>Routekaarten</strong>
<small>Opgeslagen routes · eenmalig aangevuld indien nodig</small>
</div>
<div className="route-map-dock-list">{maps.map(map => { const configuredRoute = routes.find(route => route.location_key === map.location_key && norm(route.mode) === norm(map.mode)); const configured = configuredRoute && latest(state.versions || [], item => item.route_id === configuredRoute.id); return <article className="route-map-item" key={`${map.route_id}-${map.mode}-${map.origin_location || 'home'}`}><button type="button" onClick={() => setSelectedMap({ ...map, worker_name: worker?.name, configured_kms: configured?.kms })}>
<span>⌁</span>
<span>
<strong>{map.origin_location ? `${map.origin_location} → ${map.location}` : map.location}</strong>
<small>{map.mode}</small>
</span>
<b>{map.kms} km</b>
<em>Kaart →</em>
</button><RouteCorrection routeId={map.route_id} workerId={workerId} state={state} save={save} /></article> })}{!maps.length && <p>Nog geen opgeslagen routeafstanden.</p>}</div>
</section>
</WorkerDialogBase>{selectedMap && <RouteMapModal route={selectedMap} csrf={state.csrf} revision={state.revision} onClose={() => setSelectedMap(null)} />}</>
}

function Employees({ state, onSelect }) {
  const [query, setQuery] = useState('')
  const workers = state.workers.filter(worker => worker.name.toLowerCase().includes(query.toLowerCase()))
  return <>
<header className="simple-header">
<p className="eyebrow">BEHEER</p>
<h1>Werknemers</h1>
<p>{state.workers.length} werknemers met adres-, loonnummer- en vervoerhistoriek.</p>
</header>
<input className="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Zoek werknemer" />
<div className="list">{workers.map(worker => { const reference = latest(state.external_references || [], item => item.worker_id === worker.id); const address = latest(state.addresses || [], item => item.worker_id === worker.id); return <button className="list-row" key={worker.id} onClick={() => onSelect(worker.id)}>
<div className="avatar">{worker.name.slice(0, 1)}</div>
<div>
<strong>{worker.name}</strong>
<small>{reference?.external_reference || 'Loonnummer ontbreekt'} · {addressLabel(address?.address)}</small>
</div>
<span>Bekijken →</span>
</button> })}</div>
</>
}

function LocationDialogBase({ locationKey, state, onClose, save, children }) {
  const location = state.physical_locations.find(item => item.key === locationKey)
  if (!location) return null
  const address = latest(state.location_addresses || [], item => item.location_key === location.key)
  const routeCount = new Set(state.routes.filter(route => route.location_key === location.key).map(route => route.worker_id)).size
  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
<section className="modal">
<button className="close" onClick={onClose}>×</button>
<p className="eyebrow">WERKLOCATIE</p>
<h2>{location.name}</h2>
<div className="profile-summary">
<div>
<small>Adres</small>
<strong>{address ? `${address.address.street} ${address.address.number}, ${address.address.city}` : 'Ontbreekt'}</strong>
</div>
<div>
<small>Werknemersroutes</small>
<strong>{routeCount}</strong>
</div>
<div>
<small>Klanten</small>
<strong>{location.customers.length}</strong>
</div>
</div>
<h3>Gekoppelde klanten</h3>
<div className="tags">{location.customers.map(customer => <span key={customer}>{customer}</span>)}</div>
<details className="profile-form" open={!address}>
<summary>Adres toevoegen of aanpassen</summary>
<form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('location_address_save', { location: location.name, valid_from: form.get('valid_from'), address: addressFrom(form, 'location_'), reason: form.get('reason') }) }}>
<AddressFields prefix="location_" />
<div className="form-grid">
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={today()} required />
</Field>
<Field label="Reden">
<input name="reason" defaultValue="Locatieadres aangepast door HR" required />
</Field>
</div>
<button className="secondary">Adres opslaan</button>
</form>
</details>
{children}
</section>
</div>
}

function LocationDialog({ locationKey, state, onClose, save }) {
  const [selectedMap, setSelectedMap] = useState(null)
  const location = state.physical_locations.find(item => item.key === locationKey)
  const maps = (state.route_maps || []).filter(route => route.location_key === locationKey)
  return <>
<LocationDialogBase locationKey={locationKey} state={state} onClose={onClose} save={save}>
<section className="route-map-dock" aria-label="Routekaarten locatie">
<div>
<strong>Routes naar {location?.name}</strong>
<small>Per werknemer en vervoersmiddel</small>
</div>
<div className="route-map-dock-list">{maps.map(map => { const worker = state.workers.find(item => item.id === map.worker_id); return <article className="route-map-item" key={`${map.route_id}-${map.worker_id}-${map.mode}`}><button type="button" onClick={() => setSelectedMap({ ...map, worker_name: worker?.name })}>
<span>⌁</span>
<span>
<strong>{worker?.name || 'Werknemer'}</strong>
<small>{map.mode}</small>
</span>
<b>{map.kms} km</b>
<em>Kaart →</em>
</button><RouteCorrection routeId={map.route_id} workerId={map.worker_id} state={state} save={save} /></article> })}{!maps.length && <p>Nog geen opgeslagen routeafstanden naar deze locatie.</p>}</div>
</section>
</LocationDialogBase>{selectedMap && <RouteMapModal route={selectedMap} csrf={state.csrf} revision={state.revision} onClose={() => setSelectedMap(null)} />}</>
}

function Locations({ state, onSelect }) { return <>
<header className="simple-header">
<p className="eyebrow">BEHEER</p>
<h1>Locaties</h1>
<p>Fysieke locaties, adressen en gekoppelde klanten.</p>
</header>
<div className="location-grid">{state.physical_locations.map(location => { const address = latest(state.location_addresses || [], item => item.location_key === location.key); return <button className="location" onClick={() => onSelect(location.key)} key={location.key}>
<div className="location-icon">⌖</div>
<h3>{location.name}</h3>
<p>{address ? `${address.address.postal_code} ${address.address.city}` : 'Adres controleren'}</p>
<small>{location.customers.length} gekoppelde klanten</small>
</button> })}</div>
</> }

function CandidateQueue({ state, save }) {
  const addressCandidates = (state.address_candidates || []).filter(item => item.status === 'REVIEW')
  const referenceCandidates = (state.external_reference_candidates || []).filter(item => item.status === 'REVIEW')
  const suggestedWorker = candidate => candidate.worker_id || state.workers.find(worker => norm(worker.name) === norm(candidate.name))?.id || ''
  const workerOptions = <>{state.workers.map(worker => <option value={worker.id} key={worker.id}>{worker.name}</option>)}</>
  return <section className="technical-section">
<div className="technical-section-head">
<div><p className="eyebrow">IMPORTCONTROLE</p><h2>Geïmporteerde kandidaten</h2></div>
<span className={addressCandidates.length + referenceCandidates.length ? 'count attention' : 'count'}>{addressCandidates.length + referenceCandidates.length} te beoordelen</span>
</div>
{!addressCandidates.length && !referenceCandidates.length ? <div className="empty compact"><span>✓</span><strong>Geen kandidaten meer te beoordelen</strong></div> : <div className="candidate-grid">
{addressCandidates.map(candidate => <form className="candidate-card" key={`address-${candidate.id}`} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('address_link', { candidate_id: candidate.id, worker_id: Number(form.get('worker_id')), reason: form.get('reason') }) }}>
<span>Woonadres</span><h3>{candidate.name}</h3><p>{addressLabel(candidate.address)}</p>
<Field label="Koppelen aan werknemer"><select name="worker_id" defaultValue={suggestedWorker(candidate)} required><option value="">Kies werknemer</option>{workerOptions}</select></Field>
<Field label="Reden"><input name="reason" defaultValue="Geïmporteerd adres handmatig gecontroleerd" required /></Field>
<div className="candidate-actions"><button className="primary">Koppelen</button><button type="button" className="secondary" onClick={event => { const reason = event.currentTarget.form.elements.reason; if (!reason.reportValidity()) return; save('address_ignore', { candidate_id: candidate.id, reason: reason.value }) }}>Negeren</button></div>
</form>)}
{referenceCandidates.map(candidate => <form className="candidate-card" key={`reference-${candidate.id}`} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save('external_reference_link', { candidate_id: candidate.id, worker_id: Number(form.get('worker_id')), reason: form.get('reason') }) }}>
<span>Loonnummer</span><h3>{candidate.name}</h3><p>Extern loonnummer: <strong>{candidate.external_reference}</strong></p>
<Field label="Koppelen aan werknemer"><select name="worker_id" defaultValue={suggestedWorker(candidate)} required><option value="">Kies werknemer</option>{workerOptions}</select></Field>
<Field label="Reden"><input name="reason" defaultValue="Geïmporteerd loonnummer handmatig gecontroleerd" required /></Field>
<div className="candidate-actions"><button className="primary">Koppelen</button><button type="button" className="secondary" onClick={event => { const reason = event.currentTarget.form.elements.reason; if (!reason.reportValidity()) return; save('external_reference_ignore', { candidate_id: candidate.id, reason: reason.value }) }}>Negeren</button></div>
</form>)}</div>}
</section>
}

function GeocodeReview({ item, owner, kind, save }) {
  const geocode = item.geocode
  const result = geocode?.result || {}
  const status = item.geocode_status || 'NOT_REQUESTED'
  const requestAction = kind === 'location' ? 'location_geocode' : 'address_geocode'
  return <article className={`geocode-card ${status.toLowerCase()}`}>
<div className="geocode-card-head"><div><strong>{owner}</strong><small>{kind === 'location' ? 'Werklocatie' : 'Werknemer'} · {addressLabel(item.address)}</small></div><span>{status === 'REVIEW' ? 'Nakijken' : status === 'NO_MATCH' ? 'Geen match' : status === 'ERROR' ? 'Fout' : 'Niet aangevraagd'}</span></div>
{result.label && <p><strong>Mapbox:</strong> {result.label}</p>}{result.message && <p>{result.message}</p>}
{status === 'NOT_REQUESTED' && <button className="secondary" onClick={() => save(requestAction, { address_id: item.id, consent: true })}>Coördinaten aanvragen</button>}
{status === 'REVIEW' && <form onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save(kind === 'location' ? 'location_geocode_review' : 'geocode_review', { address_id: item.id, accept: true, confirm_uncertain: form.get('confirm_uncertain') === 'on', reason: form.get('reason') }) }}>
<p>Nauwkeurigheid: {result.accuracy || 'onbekend'} · vertrouwen: {result.confidence || 'onbekend'}</p>
{!result.eligible && <label className="check"><input type="checkbox" name="confirm_uncertain" /> Ik heb deze onzekere locatie handmatig gecontroleerd</label>}
<Field label="Reden"><input name="reason" defaultValue="Mapbox-resultaat handmatig gecontroleerd" required /></Field>
<div className="candidate-actions"><button className="primary">Bevestigen</button><button type="button" className="secondary" onClick={event => { const form = event.currentTarget.form; const reason = form.elements.reason; if (!reason.reportValidity()) return; save(kind === 'location' ? 'location_geocode_review' : 'geocode_review', { address_id: item.id, accept: false, reason: reason.value }) }}>Afwijzen</button></div>
</form>}
{(status === 'NO_MATCH' || status === 'ERROR') && <p className="hint">Pas het opgeslagen adres aan om een nieuwe, unieke aanvraag mogelijk te maken. Dezelfde mislukte aanvraag wordt bewust niet automatisch herhaald.</p>}
</article>
}

function TechnicalManagement({ state, save, onRouteExport, busy }) {
  const currentRows = (rows, key) => { const selected = new Map(); for (const row of rows.filter(item => item.valid_from <= today()).sort((a, b) => a.valid_from.localeCompare(b.valid_from) || a.id - b.id)) selected.set(row[key], row); return [...selected.values()] }
  const workerAddresses = currentRows(state.addresses || [], 'worker_id')
  const locationAddresses = currentRows(state.location_addresses || [], 'location_key')
  const attention = [
    ...workerAddresses.filter(item => item.geocode_status !== 'CONFIRMED').map(item => ({ item, kind: 'worker', owner: state.workers.find(worker => worker.id === item.worker_id)?.name || 'Onbekende werknemer' })),
    ...locationAddresses.filter(item => item.geocode_status !== 'CONFIRMED').map(item => ({ item, kind: 'location', owner: item.location }))
  ]
  const routes = state.route_distances || []
  const readyRoutes = routes.filter(item => item.status === 'READY').length
  const corrections = routes.reduce((total, item) => total + (item.overrides || []).length + (item.transfer_override ? 1 : 0), 0)
  const automatic = state.automatic_routes || {}
  const report = automatic.report || {}
  return <>
<header className="simple-header"><p className="eyebrow">SYSTEEMBEHEER</p><h1>Technisch beheer</h1><p>Mapbox-verwerking, routecontrole, echte afstandscorrecties en geïmporteerde gegevens op één plaats.</p></header>
<section className="technical-stats">
<article><span>Mapbox</span><strong>{state.mapbox_configured ? 'Verbonden' : 'Token ontbreekt'}</strong><small>{automatic.enabled ? 'Automatisch actief' : 'Automatisch uitgeschakeld'}</small></article>
<article><span>Verwerking</span><strong>{automatic.status || 'Onbekend'}</strong><small>{report.routes || 0} routes · {report.errors || 0} fouten in laatste run</small></article>
<article><span>Routecache</span><strong>{readyRoutes} gereed</strong><small>{routes.length - readyRoutes} niet gereed · {corrections} HR-correcties</small></article>
<article><span>Controle</span><strong>{attention.length} adressen</strong><small>{report.attention_results || 0} aandachtspunten in laatste run</small></article>
</section>
<section className="technical-section">
<div className="technical-section-head"><div><p className="eyebrow">AUTOMATISCHE VERWERKING</p><h2>Mapbox en routes</h2></div><span className={`status ${automatic.status === 'DONE' ? 'success' : automatic.status === 'ERROR' || automatic.status === 'BLOCKED' ? 'warning' : ''}`}>{automatic.status}</span></div>
<p>Nieuwe adressen en ontbrekende routes worden alleen aangevraagd wanneer automatische verwerking actief is. Opgeslagen resultaten worden nooit stil opnieuw aangevraagd.</p>
<div className="technical-actions"><button className="primary" disabled={busy || !state.mapbox_configured} onClick={() => save('automatic_process', {})}>Verwerking starten of hervatten</button><button className="secondary" disabled={busy} onClick={() => save('automatic_settings', { enabled: !automatic.enabled, consent: !automatic.enabled })}>{automatic.enabled ? 'Automatische verwerking uitschakelen' : 'Automatische verwerking inschakelen'}</button><button className="secondary" disabled={busy || !state.matching?.run_id} onClick={onRouteExport}>Controlebestand downloaden</button></div>
<p className="hint">Het controlebestand bevat alle opgeslagen afstanden en behouden shiften van de geselecteerde exportverwerking.</p>
</section>
<section className="technical-section">
<div className="technical-section-head"><div><p className="eyebrow">GEOCODERING</p><h2>Adresresultaten nakijken</h2></div><span className={attention.length ? 'count attention' : 'count'}>{attention.length} aandachtspunten</span></div>
{attention.length ? <div className="geocode-grid">{attention.map(entry => <GeocodeReview key={`${entry.kind}-${entry.item.id}`} {...entry} save={save} />)}</div> : <div className="empty compact"><span>✓</span><strong>Alle huidige adressen hebben bevestigde coördinaten</strong></div>}
</section>
<CandidateQueue state={state} save={save} />
<section className="technical-section"><div className="technical-section-head"><div><p className="eyebrow">AFSTANDSCORRECTIES</p><h2>Waar pas je echte kilometers aan?</h2></div></div><p>Open een werknemer of locatie en klap bij de juiste route <strong>‘Echte afstand corrigeren’</strong> open. Mapbox blijft als bewijs bewaard; HR-correcties en herstelacties krijgen een afzonderlijke historie.</p></section>
</>
}

const tariffTypes = {
  standard: { title: 'Gewone auto', short: 'Standaard', description: 'Dagbedrag volgens enkele woon-werkafstand.', action: 'car_tariff', stateKey: 'car_tariffs', tone: 'green' },
  special: { title: 'Auto vroeg/laat', short: 'Vroeg/laat', description: 'Speciale tabel voor bevestigde vroege of late prestaties.', action: 'special_car_tariff', stateKey: 'special_car_tariffs', tone: 'amber' },
  extra48: { title: '48u-oproep', short: '48u', description: 'Enkele afstand × 2 × afzonderlijk kilometertarief.', action: 'extra_shift_tariff', stateKey: 'extra_shift_tariffs', tone: 'blue' },
  bicycle: { title: 'Fietsvergoeding', short: 'Fiets', description: 'Enkele fietsafstand × 2 × kilometertarief.', action: 'bicycle_tariff', stateKey: 'bicycle_tariffs', tone: 'mint' }
}

function TariffHistory({ versions, table }) {
  return <details className="tariff-history">
<summary>Versiehistoriek ({versions.length})</summary>
<div>{versions.slice().reverse().map(version => <article key={version.id}>
<span>v{version.id}</span>
<div>
<strong>Geldig vanaf {version.valid_from}</strong>
<small>{version.reason}</small>
<small>Bron: {version.source}</small>
</div>
<b>{table ? `${version.data.bands.length} regels` : kmRate(version.rate_per_km)}</b>
</article>)}</div>
</details>
}

function RateTariffForm({ type, version, save, defaultValidFrom }) {
  const config = tariffTypes[type]
  return <form className="tariff-editor simple-rate-editor" key={`${type}-${version?.id || 0}`} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save(config.action, { valid_from: form.get('valid_from'), rate_per_km: form.get('rate_per_km'), reason: form.get('reason') }) }}>
<div className="tariff-form-head">
<div>
<span>Nieuwe versie</span>
<h3>{config.title}</h3>
<p>De bestaande versie wordt niet overschreven. Oude prestaties behouden hun oorspronkelijke tarief.</p>
</div>
<div className="formula-preview">
<small>Berekening</small>
<strong>{type === 'bicycle' ? 'afstand × 2 × tarief' : 'afstand × 2 × 48u-tarief'}</strong>
</div>
</div>
<div className="tariff-primary-fields">
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={defaultValidFrom} required />
</Field>
<Field label="Bedrag per kilometer">
<div className="money-input">
<span>€</span>
<input name="rate_per_km" inputMode="decimal" defaultValue={version?.rate_per_km || ''} required />
</div>
<small>Maximaal vier decimalen.</small>
</Field>
<Field label="Reden van wijziging">
<input name="reason" defaultValue={`Nieuw ${config.title.toLowerCase()}tarief bevestigd door HR`} required />
</Field>
</div>
<div className="tariff-save-bar">
<p>
<strong>Let op:</strong> dit tarief wordt toegepast vanaf de gekozen datum.</p>
<button className="primary">Nieuwe tariefversie opslaan</button>
</div>
</form>
}

function TableTariffForm({ type, version, save, defaultValidFrom }) {
  const config = tariffTypes[type]
  const [bands, setBands] = useState(() => (version?.data?.bands || []).map(item => ({ ...item })))
  const update = (index, amount) => setBands(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, amount } : item))
  return <form className="tariff-editor" key={`${type}-${version?.id || 0}`} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); save(config.action, { valid_from: form.get('valid_from'), extra_per_km: form.get('extra_per_km'), reason: form.get('reason'), bands }) }}>
<div className="tariff-form-head">
<div>
<span>Nieuwe tabelversie</span>
<h3>{config.title}</h3>
<p>Controleer alle bedragen. De tabel moet zonder gaten de volledige afstand van 1 tot 60 km bevatten.</p>
</div>
<div className="formula-preview">
<small>Boven 60 km</small>
<strong>60 km-bedrag + extra/km</strong>
</div>
</div>
<div className="tariff-primary-fields">
<Field label="Geldig vanaf">
<input name="valid_from" type="date" defaultValue={defaultValidFrom} required />
</Field>
<Field label="Extra bedrag per km boven 60 km">
<div className="money-input">
<span>€</span>
<input name="extra_per_km" inputMode="decimal" defaultValue={version?.data?.extra_per_km || ''} required />
</div>
</Field>
<Field label="Reden van wijziging">
<input name="reason" defaultValue={`Nieuwe ${config.title.toLowerCase()}tabel bevestigd door HR`} required />
</Field>
</div>
<div className="tariff-table-wrap">
<table className="tariff-table">
<thead>
<tr>
<th>Afstand</th>
<th>Bedrag per dag</th>
<th>Afstand</th>
<th>Bedrag per dag</th>
</tr>
</thead>
<tbody>{Array.from({ length: Math.ceil(bands.length / 2) }, (_, index) => { const left = bands[index], right = bands[index + Math.ceil(bands.length / 2)]; const cells = item => item ? <>
<td>
<strong>{item.from_km === item.to_km ? item.from_km : `${item.from_km}–${item.to_km}`} km</strong>
</td>
<td>
<div className="money-input compact">
<span>€</span>
<input aria-label={`Bedrag ${item.from_km} tot ${item.to_km} km`} inputMode="decimal" value={item.amount} onChange={event => update(bands.indexOf(item), event.target.value)} required />
</div>
</td>
</> : <>
<td />
<td />
</>; return <tr key={left.from_km}>{cells(left)}{cells(right)}</tr> })}</tbody>
</table>
</div>
<div className="tariff-save-bar">
<p>
<strong>Historiek blijft behouden.</strong> Alleen prestaties vanaf de ingangsdatum gebruiken deze tabel.</p>
<button className="primary">Nieuwe tabelversie opslaan</button>
</div>
</form>
}

function Settings({ state, save }) {
  const [type, setType] = useState('standard')
  const config = tariffTypes[type]
  const versions = state[config.stateKey] || []
  const current = versions.at(-1)
  const selectedMonth = state.matching?.month
  const defaultValidFrom = selectedMonth ? `${selectedMonth}-01` : today()
  return <>
<header className="simple-header settings-header">
<p className="eyebrow">CONFIGURATIE</p>
<h1>Tarieven</h1>
<p>Beheer alle vergoedingen op één plek. Nieuwe bedragen krijgen altijd een ingangsdatum; bestaande maanden en auditgegevens blijven behouden.</p>
</header>
<div className="tariff-period-notice"><span>Geselecteerde maand</span><strong>{monthLabel(selectedMonth)}</strong><p>Nieuwe versies starten standaard op {defaultValidFrom}. Pas dit alleen aan als het officiële tarief op een andere dag ingaat.</p></div>
<section className="tariff-overview">{Object.entries(tariffTypes).map(([id, item]) => { const value = (state[item.stateKey] || []).at(-1); return <button type="button" className={`tariff-type ${item.tone} ${type === id ? 'selected' : ''}`} onClick={() => setType(id)} key={id}>
<span>{item.short}</span>
<h2>{item.title}</h2>
<p>{item.description}</p>
<div>
<strong>{id === 'standard' || id === 'special' ? `${value?.data?.bands?.length || 0} tabelregels` : value ? kmRate(value.rate_per_km) : 'Niet ingesteld'}</strong>
<small>{value ? `vanaf ${value.valid_from}` : 'Actie nodig'}</small>
</div>
</button> })}</section>
<section className="current-tariff">
<div>
<p className="eyebrow">ACTIEVE SELECTIE</p>
<h2>{config.title}</h2>
<p>{config.description}</p>
</div>{current ? <div className="current-version">
<span>Huidige versie</span>
<strong>v{current.id} · {current.valid_from}</strong>
<small>{current.reason}</small>
</div> : <div className="current-version warning">
<span>Status</span>
<strong>Niet ingesteld</strong>
</div>}</section>{type === 'standard' || type === 'special' ? <TableTariffForm key={`${type}-${current?.id}-${defaultValidFrom}`} type={type} version={current} defaultValidFrom={defaultValidFrom} save={save} /> : <RateTariffForm key={`${type}-${current?.id}-${defaultValidFrom}`} type={type} version={current} defaultValidFrom={defaultValidFrom} save={save} />}<TariffHistory versions={versions} table={type === 'standard' || type === 'special'} />
</>
}

function App({ auth }) {
  const [state, setState] = useState(null), [matching, setMatching] = useState(null), [page, setPage] = useState('overview')
  const [analytics, setAnalytics] = useState(null), [analyticsLoading, setAnalyticsLoading] = useState(false), [analyticsError, setAnalyticsError] = useState('')
  const [workerId, setWorkerId] = useState(null), [locationKey, setLocationKey] = useState(null)
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [error, setError] = useState('')
  const data = useMemo(() => deriveDashboard(state, matching), [state, matching])

  async function load(messageAfter = '', preferredMonth = undefined) { setError(''); const response = await fetch('/api/state'); if (!response.ok) throw new Error('Backend niet bereikbaar. Start eerst scripts/manage_transport.py.'); const next = await response.json(); const remembered = preferredMonth === undefined ? (matching?.month || sessionStorage.getItem('hr-selected-month')) : preferredMonth; const preferredRun = remembered && next.matching_runs?.find(run => run.month === remembered); let selected = next.matching; if (preferredRun && preferredRun.id !== selected?.run_id) { const selectedResponse = await fetch(`/api/matching/run?id=${preferredRun.id}`); if (!selectedResponse.ok) throw new Error('Geselecteerde maand laden mislukt.'); selected = await selectedResponse.json() } setState({ ...next, matching: selected }); setMatching(selected); if (selected?.month) sessionStorage.setItem('hr-selected-month', selected.month); if (messageAfter) setMessage(messageAfter) }
  useEffect(() => { load().catch(reason => setError(reason.message)) }, [])
  useEffect(() => {
    if (page !== 'analytics' || !state) return
    let active = true
    setAnalyticsLoading(true); setAnalyticsError('')
    fetch('/api/analytics').then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Analytics laden mislukt.'); return body })
      .then(body => { if (active) setAnalytics(body) })
      .catch(reason => { if (active) setAnalyticsError(reason.message) })
      .finally(() => { if (active) setAnalyticsLoading(false) })
    return () => { active = false }
  }, [page, state?.revision])
  useEffect(() => { if (busy || (!message && !error)) return; const timer = setTimeout(() => { setMessage(''); setError('') }, error ? 9000 : 6500); return () => clearTimeout(timer) }, [busy, message, error])
  async function save(action, payload) { const batchTransport = action === 'transport_default'; setBusy(true); setError(''); setMessage(batchTransport ? 'Vervoerswijze opslaan…' : 'Wijziging opslaan en maand herberekenen…'); try { const response = await fetch(`/api/action/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf }, body: JSON.stringify({ revision: state.revision, data: payload }) }); const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || 'Opslaan mislukt.'); setMessage('Wijziging opgeslagen. Actuele gegevens laden…'); await load(batchTransport ? 'Vervoer opgeslagen. Pas eventueel andere locaties aan en herbereken daarna één keer via Acties.' : 'Opgeslagen. De actuele maand is opnieuw gecontroleerd.') } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }
  async function refresh() { setBusy(true); setError(''); setMessage('Gegevens vernieuwen…'); try { await load('Gegevens zijn vernieuwd.') } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }
  async function chooseRun(runId) { setBusy(true); setError(''); setMessage('Geselecteerde maand laden…'); try { const response = await fetch(`/api/matching/run?id=${runId}`); if (!response.ok) throw new Error('Maand laden mislukt.'); const selected = await response.json(); sessionStorage.setItem('hr-selected-month', selected.month); setMatching(selected); setState(current => ({ ...current, matching: selected })); setMessage('Maand geladen.') } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }
  async function upload() { const input = document.createElement('input'); input.type = 'file'; input.accept = '.xlsx'; input.onchange = async () => { const file = input.files?.[0]; if (!file) return; if (file.size > 5_000_000) return setError('Het bestand is groter dan 5 MB.'); setBusy(true); setError(''); setMessage('Export wordt verwerkt…'); try { const content = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('Bestand lezen mislukt.')); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.readAsDataURL(file) }); const response = await fetch('/api/action/planet_upload', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf }, body: JSON.stringify({ revision: state.revision, data: { filename: file.name, content } }) }); const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || 'Upload mislukt.'); await load('Pl@net-export verwerkt.', null) } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }; input.click() }
  async function exportPayroll() { setBusy(true); setError(''); setMessage('Accerta-export wordt gemaakt…'); try { const response = await fetch('/api/payroll/export', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf }, body: JSON.stringify({ run_id: matching.run_id }) }); if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'Export mislukt.') } const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = `VERVOER-AFWIJKENDE-LONEN-${matching.month}.xlsx`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage('Accerta-export gedownload.') } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }
  async function exportRouteControl() { setBusy(true); setError(''); setMessage('Routecontrolebestand wordt gemaakt…'); try { const response = await fetch(`/api/routing/export?run_id=${matching.run_id}&csrf=${encodeURIComponent(state.csrf)}`); if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(result.error || 'Routecontrole exporteren mislukt.') } const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = `WERKNEMERSAFSTANDEN-CONTROLE-${matching.month}.xlsx`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage('Routecontrolebestand gedownload.') } catch (reason) { setError(reason.message); setMessage('') } finally { setBusy(false) } }
  function resolveAction() { setPage('actions'); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  function showEmployee(id) { setWorkerId(id); setPage('employees') }
  if (!state) return <main className="loading">
<div className="loader" />
<h1>HR Vervoerskosten</h1>
<p>{error || 'Backend laden…'}</p>
<button onClick={() => load().catch(reason => setError(reason.message))}>Opnieuw proberen</button>
</main>
  return <div className={`app ${busy ? 'app-busy' : ''}`}>
<aside>
<div className="brand">
<img src="/icts-belgium.png" alt="ICTS Belgium" />
<div>
<strong>Vervoerskosten</strong>
<small>ICTS Belgium · HR</small>
</div>
</div>
<nav>{nav.map(([id, label]) => <button className={page === id ? 'active' : ''} onClick={() => setPage(id)} key={id}>{label}{id === 'actions' && data.actions.length ? <span>{data.actions.length}</span> : null}</button>)}</nav>
{auth.enabled ? <div className="signed-in-user"><span>{auth.user?.name?.split(' ').map(part => part[0]).join('').slice(0, 2) || 'MS'}</span><div><strong>{auth.user?.name}</strong><small>{auth.user?.username}</small></div><button onClick={() => window.location.assign('/api/auth/logout')}>Afmelden</button></div> : <button className="legacy settings-shortcut" onClick={() => setPage('settings')}>Tarieven beheren →</button>}
</aside>
<main className="content">
<div className="toolbar">
<MonthPicker state={state} matching={matching} onChange={chooseRun} />
<button className="text-button" disabled={busy} onClick={upload}>＋ Nieuwe export</button>
<button className="text-button" disabled={busy} onClick={refresh}>{busy && message.startsWith('Gegevens') ? 'Bezig…' : '↻ Vernieuwen'}</button>
</div>{page === 'overview' && <Overview data={data} onUpload={upload} onExport={exportPayroll} onResolve={resolveAction} busy={busy} />}{page === 'actions' && <ActionCenter state={state} matching={matching} data={data} save={save} onEmployee={showEmployee} onReview={() => setPage('review')} />}{page === 'review' && <MonthReview matching={matching} state={state} save={save} />}{page === 'analytics' && <Analytics analytics={analytics} month={matching?.month} loading={analyticsLoading} error={analyticsError} />}{page === 'employees' && <Employees state={state} onSelect={setWorkerId} />}{page === 'locations' && <Locations state={state} onSelect={setLocationKey} />}{page === 'technical' && <TechnicalManagement state={state} save={save} onRouteExport={exportRouteControl} busy={busy} />}{page === 'settings' && <Settings state={state} save={save} />}</main>{workerId && <WorkerDialog workerId={workerId} state={state} onClose={() => setWorkerId(null)} save={save} />}{locationKey && <LocationDialog locationKey={locationKey} state={state} onClose={() => setLocationKey(null)} save={save} />}{busy && <div className="activity-shield" role="status" aria-live="assertive"><div className="activity-toast busy"><div className="loader small" /><div><strong>{message || 'Even geduld…'}</strong><span>Sluit dit venster niet tijdens de verwerking.</span></div></div></div>}{!busy && error && <div className="activity-toast error" role="alert"><b>!</b><div><strong>Actie mislukt</strong><span>{error}</span></div><button onClick={() => setError('')} aria-label="Melding sluiten">×</button></div>}{!busy && message && <div className="activity-toast success" role="status"><b>✓</b><div><strong>Gelukt</strong><span>{message}</span></div><button onClick={() => setMessage('')} aria-label="Melding sluiten">×</button></div>}</div>
}

function AuthGate() {
  const [auth, setAuth] = useState(null)
  const [error, setError] = useState('')
  const [loginBusy, setLoginBusy] = useState(false)
  const check = () => { setError(''); fetch('/api/auth/status').then(async response => { if (!response.ok) throw new Error('Authenticatieservice niet bereikbaar.'); return response.json() }).then(setAuth).catch(reason => setError(reason.message)) }
  const localLogin = async event => { event.preventDefault(); const form = new FormData(event.currentTarget); setLoginBusy(true); setError(''); try { const response = await fetch('/api/auth/local-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: form.get('username'), password: form.get('password') }) }); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.error || 'Aanmelden mislukt.'); check() } catch (reason) { setError(reason.message) } finally { setLoginBusy(false) } }
  useEffect(check, [])
  if (!auth) return <main className="login-page"><div className="login-card"><img src="/icts-belgium.png" alt="ICTS Belgium" /><div className="loader" /><h1>HR Vervoerskosten</h1><p>{error || 'Beveiliging controleren…'}</p>{error && <button className="secondary" onClick={check}>Opnieuw proberen</button>}</div></main>
  if (auth.enabled && !auth.authenticated) return <main className="login-page"><div className="login-card"><img src="/icts-belgium.png" alt="ICTS Belgium" /><p className="eyebrow">BEVEILIGDE HR-OMGEVING</p><h1>Welkom</h1>{auth.provider === 'microsoft' ? <><p>Meld je aan met je ICTS Microsoft-account. De applicatie bewaart geen wachtwoorden.</p><button className="microsoft-login" onClick={() => window.location.assign('/api/auth/login')}><span aria-hidden="true"><i /><i /><i /><i /></span>Aanmelden met Microsoft</button>{auth.required_role && <small>Toegang vereist de rol <strong>{auth.required_role}</strong>.</small>}</> : <><p>Meld je aan met het tijdelijke lokale beheeraccount. Het wachtwoord wordt uitsluitend als Argon2id-hash gecontroleerd.</p><form className="local-login-form" onSubmit={localLogin}><Field label="Gebruikersnaam"><input name="username" autoComplete="username" required autoFocus /></Field><Field label="Wachtwoord"><input name="password" type="password" autoComplete="current-password" required /></Field>{error && <div className="login-error" role="alert">{error}</div>}<button className="primary" disabled={loginBusy}>{loginBusy ? 'Controleren…' : 'Aanmelden'}</button></form></>}</div></main>
  return <App auth={auth} />
}

createRoot(document.getElementById('root')).render(<React.StrictMode>
<AuthGate />
</React.StrictMode>)
