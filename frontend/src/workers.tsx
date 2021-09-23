import * as React from "react";
import { fetchPost, Nav, Worker } from "./base";
import { StringEdit, useEditables } from "./utils";

const WorkerEdit: React.FC<{worker: Worker, save: (worker: Worker) => Promise<void>}> = (props) => {
	const w = props.worker;
	const loginUrl = `${location.origin}/login/#` + new URLSearchParams({phone: w.phone, password: w.login_secret});
	const [edited, values, [name, phone, note, active]] = useEditables(
		[w.name, w.phone, w.note, w.active + ""]
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
		<td><button onClick={() => {
			navigator.clipboard.writeText(loginUrl).catch(() => window.prompt("Login-link", loginUrl));
		}}>Kopiér login-link</button></td>
	</tr>;
}

const ImportWorkers: React.FC<{reload: () => void, workers: {[idString: string]: Worker}}> = (props) => {
	const [value, setValue] = React.useState("");
	const [errors, setErrors] = React.useState("");
	const doImport = React.useCallback(
		async () => {
			const existingName: {[name: string]: 1} = {};
			const existingPhone: {[phone: string]: 1} = {};
			const errors = [];
			for (const worker of Object.values(props.workers)) {
				existingName[worker.name] = 1;
				existingPhone[worker.phone] = 1;
			}
			const lines = value.split("\n").map((line: string) => line.trim().split("\t").map((cell: string) => cell.trim()));
			// Vagttager,Telefon,Spl.stud,H5,H6
			const [_headName, _headPhone, ...headCrosses] = lines[0];
			const newWorkers = [];
			for (const row of lines.slice(1, lines.length)) {
				const [name, phone, ...crosses] = row;
				if (!name || !phone) {
					console.log("Skip", {name, phone});
					continue;
				}
				if (existingName[name]) {
					errors.push(`Navn findes allerede: '${name}'`);
				}
				if (existingPhone[phone]) {
					errors.push(`Telefon findes allerede: '${phone}'`);
				}
				const note = headCrosses.filter((_, i) => crosses[i]).join(", ");
				newWorkers.push({name, phone, note});
			};
			if (errors.length > 0) {
				setErrors(errors.join("; "));
				return;
			}
			if (newWorkers.length === 0) {
				setErrors("Blank");
				return;
			}
			const res = await fetchPost("/api/v0/worker/", newWorkers);
			if (!res.ok) {
				setErrors(`Serverfejl: HTTP ${res.status}`);
			}
			await res.json();
			setErrors("");
			props.reload();
		},
		[props.workers, value],
	);
	return <div>
		<h2>Importér fra regneark</h2>
		<div>
			<textarea className="sp_import_textarea" value={value} onChange={(e) => setValue(e.target.value)} />
		</div>
		<div>
			<button onClick={() => doImport()}>Importér</button>
		</div>
		{errors !== "" && 
		<div className="sp_error">
			{errors}
		</div>}
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
	return <>
		<div>
			<input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Søg" />
		</div>
		<h2>Vagttagere ({props.loaded ? active.length : "..."})</h2>
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
	return <>
		<Nav current="workers" />
		<div>
			<Workers loaded={loaded} workers={workers.current} save={save} />
			<ImportWorkers reload={reload} workers={workers.current} />
		</div>
	</>;
}