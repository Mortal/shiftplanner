import * as React from "react";
import { fetchPost, Topbar, Worker, WorkplaceSettings, WorkplaceSettingsContext } from "./base";
import { StringEdit, useEditables } from "./utils";

const encodeQuery = (params: {[k: string]: string}) => {
	return Object.entries(params).map(([k, v]) => `${window.encodeURIComponent(k)}=${window.encodeURIComponent(v)}`).join("&");
};

const WorkerLoginLinks: React.FC<{worker: Worker, settings: WorkplaceSettings}> = (props) => {
	const w = props.worker;
	const s = props.settings;
	if (w.phone == null || w.phone === "") return <>(intet telefonnummer)</>;
	if (w.login_secret == null || w.login_secret === "") return <>(intet kodeord)</>;
	const loginUrl = `${location.origin}/login/#` + new URLSearchParams({phone: w.phone, password: w.login_secret});
	const subject = s.login_email_subject || "";
	const repl = {name: w.name, link: loginUrl};
	const body = (s.login_email_template || "").replace(/\{(name|link)\}/g, (_, v: string) => (repl as any)[v]);
	const smsBody = (s.login_sms_template || "").replace(/\{(name|link)\}/g, (_, v: string) => (repl as any)[v]);
	const mailtoUri = `mailto:?${encodeQuery({subject, body})}`;
	const cc = (w.phone.startsWith("+") || w.phone.startsWith("0")) ? "" : (s.country_code || "");
	const smsUri = `sms:${cc}${w.phone}?${encodeQuery({body: smsBody})}`;
	const myshiftsUri = `/myshifts/?wid=${w.id}`;
	return <>
		<button onClick={() => {
			navigator.clipboard.writeText(loginUrl).catch(() => window.prompt("Login-link", loginUrl));
		}}>Kopiér login-link</button>
		{" · "}
		<a href={mailtoUri} target="_blank">Send email med login-link</a>
		{" · "}
		<a href={smsUri} target="_blank">Send SMS med login-link</a>
		{" · "}
		<a href={myshiftsUri} target="_blank">Liste over bookinger</a>
	</>;
}

const WorkerEdit: React.FC<{worker: Worker, save: (worker: Worker) => Promise<void>}> = (props) => {
	const w = props.worker;
	const [edited, values, [name, phone, note, active]] = useEditables(
		[w.name, w.phone || "", w.note, w.active + ""]
	)

	const save = React.useCallback(async () => {
		if (!edited) return;
		const [name, phone, note, active] = values;
		props.save(
			{
				...props.worker,
				name,
				phone,
				note,
				active: active === "true",
			}
		);
	}, [edited, ...values]);

	return <tr>
		<td><StringEdit placeholder="Navn" state={name} save={save} /></td>
		<td><StringEdit placeholder="Telefon" state={phone} save={save} /></td>
		<td><StringEdit placeholder="Note" state={note} save={save} /></td>
		<td>
			<input type="checkbox" checked={active[0] === "true"} onChange={(e) => active[1](e.target.checked + "")} />
		</td>
		<td><input type="button" value="Gem" onClick={() => save()} disabled={!edited} /></td>
		<td>
			<WorkplaceSettingsContext.Consumer>
				{(value: WorkplaceSettings) => <WorkerLoginLinks worker={props.worker} settings={value} />}
			</WorkplaceSettingsContext.Consumer>
		</td>
	</tr>;
}

interface NewWorker {
	name: string;
	phone: string;
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
		newWorkers.push({name, phone, note});
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
	const errors = [];
	for (const worker of existing) {
		existingName[worker.name] = 1;
		if (worker.phone) existingPhone[worker.phone] = 1;
	}
	for (const {name, phone} of newWorkers) {
		if (name === "") {
			errors.push("Vagttager mangler navn");
			continue;
		}
		if (phone === "") {
			errors.push("Vagttager mangler telefonnummer");
			continue;
		}
		if (existingName[name]) {
			errors.push(`Navn findes allerede: '${name}'`);
		}
		if (existingPhone[phone]) {
			errors.push(`Telefonnummer findes allerede: '${phone}'`);
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
	const [workers, setWorkers] = React.useState<NewWorker[]>([{name: "", phone: "", note: ""}]);
	const [errors, setErrors] = React.useState<string[]>([]);
	const doImport = React.useCallback(
		async () => {
			const workersFilter = workers.filter((w) => w.name !== "" || w.phone !== "");
			console.log({workersFilter});
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
							const rest = (i === workers.length - 1) ? [{name: "", phone: "", note: ""}] : workers.slice(i + 1);
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

const Workers: React.FC<{
	workers: {[idString: string]: Worker},
	loaded: boolean,
	save: (worker: Worker) => Promise<void>,
}> = (props) => {
	const [search, setSearch] = React.useState("");
	const active: Worker[] = [];
	const inactive: Worker[] = [];
	for (const w of Object.values(props.workers)) {
		if (`${w.name}\n${w.note}\n${w.phone}`.indexOf(search) === -1) continue;
		if (w.active) active.push(w);
		else inactive.push(w);
	}
	active.sort((a, b) => a.name.localeCompare(b.name));
	inactive.sort((a, b) => a.name.localeCompare(b.name));
	return <>
		<div>
			<input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Søg" />
		</div>
		<h2>Vagttagere ({props.loaded ? active.length : "..."})</h2>
		<div>
			<a href="/admin/worker_stats/">Vis opgørelse over bookinger</a>
		</div>
		<table>
			<tbody>
				{active.map((worker) => <WorkerEdit worker={worker} key={worker.id} save={props.save} />)}
			</tbody>
		</table>
		<h2>Inaktive ({props.loaded ? inactive.length : "..."})</h2>
		<table>
			<tbody>
				{inactive.map((worker) => <WorkerEdit worker={worker} key={worker.id} save={props.save} />)}
			</tbody>
		</table>
	</>;
};

const useFifo = () => {
	const [head, setHead] = React.useState(0);
	const [tail, setTail] = React.useState(0);
	const queue = React.useRef<(() => Promise<void>)[]>([]);
	React.useEffect(
		() => {
			(async () => {
				if (head === tail) return;
				await queue.current[head]();
				setHead(head + 1);
			})();
		},
		[head === tail, head === tail ? tail : head],
	);
	const enqueue = React.useCallback(
		(work: () => Promise<void>) => {
			queue.current.push(work);
			setTail(queue.current.length);
		},
		[],
	);
	return [head > 0 && head === tail, enqueue] as [boolean, typeof enqueue];
}

export const WorkersMain: React.FC<{}> = (_props) => {
	const [loaded, enqueue] = useFifo();
	const workers = React.useRef<{[idString: string]: any}>({});
	const workplace = React.useRef<{[idString: string]: any}>({});
	const reload = React.useCallback(
		() => {
			enqueue(async () => {
				const res = await window.fetch("/api/v0/worker/");
				const data = await res.json();
				for (const row of data.rows) workers.current[row.id + ""] = row;
			});
		},
		[],
	);
	React.useEffect(
		() => {
			reload();
			enqueue(async () => {
				const res = await window.fetch("/api/v0/workplace/");
				const data = await res.json();
				for (const row of data.rows) workplace.current[row.id + ""] = row;
			});
		},
		[],
	);
	const save = React.useCallback(
		async (worker: Worker) => {
			enqueue(async () => {
				const res = await fetchPost(`/api/v0/worker/${worker.id}/`, worker);
				if (res.ok) {
					workers.current[worker.id + ""] = {
						...workers.current[worker.id + ""],
						...worker,
					}
				}
			});
		},
		[],
	);
	const workplaceSettings = Object.values(workplace.current).length === 0 ? {} : Object.values(workplace.current)[0].settings;
	return <>
		<Topbar current="workers" />
		<div>
			<WorkplaceSettingsContext.Provider value={workplaceSettings}>
				<Workers loaded={loaded} workers={workers.current} save={save} />
				<CreateWorkers reload={reload} workers={workers.current} />
			</WorkplaceSettingsContext.Provider>
		</div>
	</>;
}
