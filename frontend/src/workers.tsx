import * as React from "react";
import { useApiWorkerStats, WorkerStatsRow, WorkerStatsEntry } from "./api";
import { fetchPost, Topbar, useFifo, useReloadableFetchJson, useRowsToIdMap, Worker, Workplace, WorkplaceSettings, WorkplaceSettingsContext } from "./base";
import { StringEdit, useEditables } from "./utils";

const encodeQuery = (params: {[k: string]: string}) => {
	return Object.entries(params).map(([k, v]) => `${window.encodeURIComponent(k)}=${window.encodeURIComponent(v)}`).join("&");
};

const asciify = (s: string) => {
	const repl: {[k: string]: string} = {
		æ: "ae",
		Æ: "AE",
		ø: "oe",
		Ø: "OE",
		å: "aa",
		Å: "AA",
		ä: "ae",
		Ä: "AE",
		ö: "oe",
		Ö: "OE",
		ü: "ue",
		Ü: "UE",
	};
	return s.replace(new RegExp(Object.keys(repl).join("|"), "g"), (k) => repl[k]);
};

const stringifyWorkerStat = (stats: AggregatedWorkerStat | null | undefined) => {
	if (stats === null) return "... bookinger";
	if (stats === undefined || stats.last == null) return "0 bookinger";
	return `${stats.count} bookinger, seneste i uge ${stats.last.isoweek} ${stats.last.isoyear}`
}

const WorkerLoginLinks: React.FC<{worker: Worker, settings: WorkplaceSettings, stats: AggregatedWorkerStat | null | undefined}> = (props) => {
	const w = props.worker;
	const s = props.settings;
	const phone = w.phone || "";
	const login_secret = w.login_secret || "";
	if (phone === "") return <>(intet telefonnummer)</>;
	if (login_secret === "") return <>(intet kodeord)</>;
	const loginUrl = `${location.origin}/login/#` + new URLSearchParams({phone: phone, password: login_secret});
	const subject = asciify(s.login_email_subject || "");
	const repl = {name: w.name, link: loginUrl};
	const body = asciify((s.login_email_template || "").replace(/\{(name|link)\}/g, (_, v: string) => (repl as any)[v]));
	const smsBody = (s.login_sms_template || "").replace(/\{(name|link)\}/g, (_, v: string) => (repl as any)[v]);
	const mailtoUri = `mailto:${window.encodeURIComponent(w.email || "")}?${encodeQuery({subject, body})}`;
	const cc = (phone.startsWith("+") || phone.startsWith("0")) ? "" : (s.country_code || "");
	const smsUri = `sms:${cc}${phone}?${encodeQuery({body: smsBody})}`;
	const myshiftsUri = `/myshifts/?wid=${w.id}`;
	return <>
		{
			phone === "" ? <button disabled>Login kræver telefonnummer</button> :
			login_secret === "" ? <button disabled>(kodeord mangler??)</button> :
			<button onClick={() => {
				navigator.clipboard.writeText(loginUrl).catch(() => window.prompt("Login-link", loginUrl));
			}}>Kopiér login-link</button>
		}
		{" · "}
		<a href={mailtoUri} target="_blank">Send email med login-link</a>
		{props.settings.enable_sms && <>
			{" · "}
			<a href={smsUri} target="_blank">Send SMS med login-link</a>
		</>}
		{" · "}
		<a href={myshiftsUri} target="_blank">
			{stringifyWorkerStat(props.stats)}
		</a>
	</>;
}

const WorkerEdit: React.FC<{worker: Worker, save: (worker: Worker) => Promise<void>, stats: AggregatedWorkerStat | null | undefined}> = (props) => {
	const w = props.worker;
	const [edited, values, [name, phone, email, note, active]] = useEditables(
		[w.name, w.phone || "", w.email || "", w.note, w.active + ""]
	)

	const save = React.useCallback(async () => {
		if (!edited) return;
		const [name, phone, email, note, active] = values;
		props.save(
			{
				...props.worker,
				name,
				phone,
				email,
				note,
				active: active === "true",
			}
		);
	}, [edited, ...values]);

	return <tr>
		<td><StringEdit placeholder="Navn" state={name} save={save} /></td>
		<td><StringEdit placeholder="Telefon" state={phone} save={save} /></td>
		<WorkplaceSettingsContext.Consumer>
			{(settings: WorkplaceSettings) =>
				settings.enable_worker_email && <td><StringEdit placeholder="Email" state={email} save={save} /></td>
			}
		</WorkplaceSettingsContext.Consumer>
		<td><StringEdit placeholder="Note" state={note} save={save} /></td>
		<td>
			<input type="checkbox" checked={active[0] === "true"} onChange={(e) => active[1](e.target.checked + "")} />
		</td>
		<td><input type="button" value="Gem" onClick={() => save()} disabled={!edited} /></td>
		<td>
			<WorkplaceSettingsContext.Consumer>
				{(settings: WorkplaceSettings) =>
					<WorkerLoginLinks
						worker={props.worker}
						settings={settings}
						stats={props.stats}
						/>}
			</WorkplaceSettingsContext.Consumer>
		</td>
	</tr>;
}

interface NewWorker {
	name: string;
	phone: string;
	email: string;
	note: string;
}

const parseWorkerCsv: (v: string) => {workers: NewWorker[], errors: null} | {errors: string[]} = (value) => {
	const lines = value
		.split("\n")
		.map((line) => line.trimEnd())
		.filter((line) => line !== "")
		.map((line) => line.split("\t").map((cell: string) => cell.trim()));
	const [_headName, _headPhone, ...headCrosses] = lines[0];
	const newWorkers = [];
	let skipped = 0;
	const existingName: {[v: string]: 1} = {};
	const existingPhone: {[v: string]: 1} = {};
	const errors = [];
	for (const row of lines.slice(1, lines.length)) {
		const [name, phone, ...crosses] = row;
		if (!name || !phone) {
			skipped += 1;
			continue;
		}
		if (existingName[name]) {
			errors.push(`Navn gentaget: '${name}'`);
		}
		if (existingPhone[phone]) {
			errors.push(`Telefon gentaget: '${phone}'`);
		}
		existingName[name] = 1;
		existingPhone[phone] = 1;
		const note = headCrosses.filter((_, i) => crosses[i]).join(", ");
		newWorkers.push({name, phone, email: "", note});
	}
	if (errors.length > 0) return {errors};
	if (skipped > 0) {
		return {errors: [`${skipped} række(r) uden telefonnummer`]};
	}
	return {workers: newWorkers, errors: null};
}

const importWorkers: (existing: Worker[], newWorkers: NewWorker[]) => Promise<{errors: string[]} | {ok: true, errors: null}> = async (existing, newWorkers) => {
	const existingName: {[name: string]: 1} = {};
	const existingPhone: {[phone: string]: 1} = {};
	const existingEmail: {[email: string]: 1} = {};
	const errors = [];
	for (const worker of existing) {
		existingName[worker.name] = 1;
		if (worker.phone) existingPhone[worker.phone] = 1;
		if (worker.email) existingEmail[worker.email] = 1;
	}
	for (const {name, phone, email} of newWorkers) {
		if (name === "") {
			errors.push("Vagttager mangler navn");
			continue;
		}
		if (existingName[name]) {
			errors.push(`Navn findes allerede: '${name}'`);
		}
		if (phone !== "" && existingPhone[phone]) {
			errors.push(`Telefonnummer findes allerede: '${phone}'`);
		}
		if (email !== "" && existingEmail[email]) {
			errors.push(`Emailadresse findes allerede: '${email}'`);
		}
	};
	if (errors.length > 0) {
		return {errors};
	}
	if (newWorkers.length === 0) {
		return {errors: ["Blank"]};
	}
	const res = await fetchPost("/api/v0/worker/", newWorkers);
	if (res.status === 400) {
		const resp = await res.json();
		if (typeof resp.error === "string") {
			return {errors: [resp.error]};
		}
	}
	if (!res.ok) {
		return {errors: [`Serverfejl: HTTP ${res.status}`]};
	}
	await res.json();
	return {ok: true, errors: null};
};

const ImportWorkersForm: React.FC<{onSubmit: (workers: NewWorker[]) => void}> = (props) => {
	const [value, setValue] = React.useState("");
	const [errors, setErrors] = React.useState<string[]>([]);
	const doImport = React.useCallback(
		() => {
			const parsed = parseWorkerCsv(value);
			if (parsed.errors) {
				setErrors(parsed.errors);
				return;
			}
			props.onSubmit(parsed.workers);
		},
		[value],
	);
	return <>
		<div>
			<textarea className="sp_import_textarea" value={value} onChange={(e) => setValue(e.target.value)} />
		</div>
		<div>
			<button onClick={() => doImport()}>Importér</button>
		</div>
		{errors.length > 0 &&
		<ul className="sp_error">
			{errors.map((e, i) => <li key={i}>{e}</li>)}
		</ul>}
	</>;
}

const CreateWorkers: React.FC<{reload: () => void, workers: {[idString: string]: Worker}}> = (props) => {
	const [workers, setWorkers] = React.useState<NewWorker[]>([{name: "", phone: "", email: "", note: ""}]);
	const [errors, setErrors] = React.useState<string[]>([]);
	const doImport = React.useCallback(
		async () => {
			const workersFilter = workers.filter((w) => w.name !== "");
			const res = await importWorkers(Object.values(props.workers), workersFilter);
			if (res.errors) {
				setErrors(res.errors);
				return;
			}
			setErrors([]);
			props.reload();
		},
		[props.workers, workers],
	);
	const [csvMode, setCsvMode] = React.useState(false);
	return <div>
		<h2>Opret nye vagttagere</h2>
		{
			csvMode
			?
			<>
			<ImportWorkersForm onSubmit={(workers) => {setWorkers(workers); setCsvMode(false);}} />
			</>
			:
			<>
			<div>
				<button onClick={() => doImport()}>Opret vagttagere</button>
			</div>
			<table>
				<tbody>
					{workers.map((worker, i) => {
						const set = (w: NewWorker) => {
							const rest = (i === workers.length - 1) ? [{name: "", phone: "", email: "", note: ""}] : workers.slice(i + 1);
							setWorkers([
								...workers.slice(0, i),
								w,
								...rest,
							])
						};
						return <tr key={i}>
							<td>
								<StringEdit
									state={[
										worker.name,
										(name) => set({...workers[i], name})
									]}
									save={() => void(0)}
									placeholder="Navn"
									/>
							</td>
							<td>
								<StringEdit
									state={[
										worker.phone,
										(phone) => set({...workers[i], phone})
									]}
									save={() => void(0)}
									placeholder="Telefon"
									/>
							</td>
							<WorkplaceSettingsContext.Consumer>
								{(settings) => settings.enable_worker_email &&
									<td>
										<StringEdit
											state={[
												worker.email,
												(email) => set({...workers[i], email})
											]}
											save={() => void(0)}
											placeholder="Email"
											/>
									</td>
								}
							</WorkplaceSettingsContext.Consumer>
							<td>
								<StringEdit
									state={[
										worker.note,
										(note) => set({...workers[i], note})
									]}
									save={() => void(0)}
									placeholder="Note"
									/>
							</td>
						</tr>;
					})}
				</tbody>
			</table>
			<div>
				<a href="#" onClick={(e) => {e.preventDefault(); setCsvMode(true);}}>Importér fra regneark</a>
			</div>
			</>
		}
		{errors.length > 0 &&
		<ul className="sp_error">
			{errors.map((e, i) => <li key={i}>{e}</li>)}
		</ul>}
	</div>
}

interface AggregatedWorkerStat {
    count: number;
    last: WorkerStatsEntry | null;
}

const aggregateWorkerStats = (entries: WorkerStatsRow[] | null) => {
	if (entries == null) return null;
	const lt = (a: WorkerStatsEntry, b: WorkerStatsEntry) =>
		(a.isoyear !== b.isoyear ? a.isoyear < b.isoyear : a.isoweek < b.isoweek);
	return new Map<number, AggregatedWorkerStat>(
		entries.map(
			({stats, ...entry}) => [
				entry.id,
				{
					count: stats.reduce((a, b) => a + b.count, 0),
					last: stats.length === 0 ? null : stats.reduce((a, b) => lt(a, b) ? b : a),
				}
			]
		)
	);
};

const useSearchableWorkers = (workers: Worker[]) => {
	const [search, setSearch] = React.useState("");
	const sorted: Worker[] = [];
	for (const w of Object.values(workers)) {
		if (`${w.name}\n${w.note}\n${w.phone}\n${w.email}`.indexOf(search) === -1) continue;
		sorted.push(w);
	}
	sorted.sort((a, b) => a.name.localeCompare(b.name));
	const component = <div>
		<input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Søg" />
	</div>;
	return [sorted, component] as const;
}

const SelectWorkerForDeletion: React.FC<{
	worker: Worker,
	workerStat: AggregatedWorkerStat | null | undefined,
	selected: boolean,
	setSelected: (worker: Worker, selected: boolean) => void,
}> = (props) => {
	const htmlFor = `SelectWorkerForDeletion${props.worker.id}`;
	return <tr>
		<td><input id={htmlFor} type="checkbox" checked={props.selected} onChange={(e) => props.setSelected(props.worker, e.target.checked)} /></td>
		<td><label htmlFor={htmlFor}>{props.worker.name}</label></td>
		<td>{stringifyWorkerStat(props.workerStat)}</td>
	</tr>;
};

const DeleteWorkers: React.FC<{
	workers: {[idString: string]: Worker},
	workerStats: WorkerStatsRow[] | null,
	loaded: boolean,
	deleteWorkers: (workers: Worker[]) => Promise<void>,
	goBack: () => void,
}> = (props) => {
	const [selected, updateSelected] = React.useState<{[workerId: string]: boolean}>({});
	const setSelected = React.useCallback((worker: Worker, s: boolean) => updateSelected(
		(selected) => ({...selected, [worker.id + ""]: s})
	), []);
	const [inactive, searchComponent] = useSearchableWorkers(
		Object.values(props.workers).filter((w) => !w.active)
	);
	const selectedWorkers = inactive.filter((w) => selected[w.id + ""]);
	const getAggregated = useAggregatedWorkerStats(props.workerStats);
	return <>
		{searchComponent}
		<h2>Slet inaktive vagttagere ({props.loaded ? inactive.length : "..."})</h2>
		<p>
			<a href="#" onClick={(e) => {e.preventDefault(); props.goBack();}}>
				Gå tilbage
			</a>
		</p>
		<table>
			<tbody>
				{inactive.map((worker) =>
					<SelectWorkerForDeletion
						worker={worker}
						workerStat={getAggregated(worker)}
						selected={!!selected[worker.id + ""]}
						setSelected={setSelected}
						key={worker.id}
						/>)}
			</tbody>
		</table>
		<p>
			<button
				disabled={selectedWorkers.length === 0}
				onClick={(e) => {e.preventDefault(); props.deleteWorkers(selectedWorkers);}}
			>
				Slet {selectedWorkers.length} inaktive vagttagere
			</button>
		</p>
	</>;
};

const useAggregatedWorkerStats = (workerStats: WorkerStatsRow[] | null) => {
	const aggregatedWorkerStats = React.useMemo(() => aggregateWorkerStats(workerStats), [workerStats]);
	return (w: Worker) => aggregatedWorkerStats == null ? null : aggregatedWorkerStats.get(w.id);
}

const Workers: React.FC<{
	workers: {[idString: string]: Worker},
	loaded: boolean,
	save: (worker: Worker) => Promise<void>,
	workerStats: WorkerStatsRow[] | null,
	goToDelete: () => void,
}> = (props) => {
	const [workers, searchComponent] = useSearchableWorkers(Object.values(props.workers));
	const getAggregated = useAggregatedWorkerStats(props.workerStats);
	const active = workers.filter((w) => w.active);
	const inactive = workers.filter((w) => !w.active);
	return <>
		{searchComponent}
		<h2>Vagttagere ({props.loaded ? active.length : "..."})</h2>
		<div>
			<a href="/admin/worker_stats/">Vis opgørelse over bookinger</a>
		</div>
		<table>
			<tbody>
				{active.map((worker) =>
					<WorkerEdit
						worker={worker}
						key={worker.id}
						save={props.save}
						stats={getAggregated(worker)}
						/>)}
			</tbody>
		</table>
		<h2>Inaktive ({props.loaded ? inactive.length : "..."})</h2>
		<p>
			<a href="#" onClick={(e) => {e.preventDefault(); props.goToDelete();}}>
				Gå til sletning af vagttagere...
			</a>
		</p>
		<table>
			<tbody>
				{inactive.map((worker) =>
					<WorkerEdit
						worker={worker}
						key={worker.id}
						save={props.save}
						stats={getAggregated(worker)}
						/>)}
			</tbody>
		</table>
	</>;
};

export const WorkersMain: React.FC<{}> = (_props) => {
	const [loaded, enqueue] = useFifo();
	const [workersJson, reloadWorkersInner] = useReloadableFetchJson<{rows: Worker[]}>();
	const reloadWorkers =
		React.useCallback(() => enqueue(() => reloadWorkersInner(window.fetch("/api/v0/worker/"))), []);
	const workers = useRowsToIdMap<Worker>(workersJson);
	const [workplaceJson, reloadWorkplace] = useReloadableFetchJson<{rows: Workplace[]}>();
	const workplaceSettings = (workplaceJson == null || !workplaceJson.rows) ? {} : workplaceJson.rows[0].settings;
	React.useEffect(
		() => {
			reloadWorkers();
			enqueue(() => reloadWorkplace(window.fetch("/api/v0/workplace/")));
		},
		[],
	);
	const save = React.useCallback(
		async (worker: Worker) => {
			enqueue(async () => {
				const res = await fetchPost(`/api/v0/worker/${worker.id}/`, worker);
				if (res.ok) {
					workers[worker.id + ""] = {
						...workers[worker.id + ""],
						...worker,
					}
				}
			});
		},
		[],
	);
	const deleteWorkers = React.useCallback(
		async (ws: Worker[]) => {
			enqueue(async () => {
				const res = await fetchPost(`/api/v0/worker_delete/`, {workers: ws});
				if (res.ok) {
					for (const w of ws){
						delete workers[w.id + ""];
					}
				}
			});
		},
		[],
	);
	const workerStats = useApiWorkerStats();
	type ViewType = "edit" | "delete";
	const [view, setView] = React.useState<ViewType>("edit");
	const setViewAndScroll = (v: ViewType) => {
		setView(v);
		window.scrollTo(0, 0);
	}
	return <>
		<Topbar current="workers" />
		<div>
			<WorkplaceSettingsContext.Provider value={workplaceSettings}>
				{view === "delete"
					? <DeleteWorkers
						loaded={loaded}
						workers={workers}
						workerStats={workerStats}
						deleteWorkers={deleteWorkers}
						goBack={() => setViewAndScroll("edit")}
						/>
					: <>
						<Workers
							loaded={loaded}
							workers={workers}
							save={save}
							workerStats={workerStats}
							goToDelete={() => setViewAndScroll("delete")}
							/>
						<CreateWorkers reload={reloadWorkers} workers={workers} />
					</>}
			</WorkplaceSettingsContext.Provider>
		</div>
	</>;
}
