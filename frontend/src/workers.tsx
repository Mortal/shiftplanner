import * as React from "react";
import { fetchPost, Nav, Worker } from "./base";

const StringEdit: React.FC<{
	state: [string, (v: string) => void],
	save: () => void,
	placeholder?: string,
}> = (props) => {
	const onKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.code !== "Enter") return;
		e.preventDefault();
		props.save();
	};
	return <input
		value={props.state[0]}
		onChange={(e) => props.state[1](e.target.value)}
		onKeyPress={onKeyPress}
		placeholder={props.placeholder}
	/>;
}

const WorkerEdit: React.FC<{worker: Worker}> = (props) => {
	const {id, name, phone, active, note, login_secret: loginSecret} = props.worker;
	const loginUrl = `/login/#` + new URLSearchParams({phone, password: loginSecret});
	const nameInput = React.useState(name);
	const phoneInput = React.useState(phone);
	const noteInput = React.useState(note);
	const activeInput = React.useState(active);
	const edited =
		nameInput[0] !== name
		|| phoneInput[0] !== phone
		|| noteInput[0] !== note
		|| activeInput[0] !== active;

	const save = React.useCallback(async () => {
		if (!edited) return;
		const v = {
			name: nameInput[0],
			phone: phoneInput[0],
			note: noteInput[0],
			active: activeInput[0],
		};
		const res = await fetchPost(`/api/v0/worker/${id}/`, v);
		if (res.ok) {
			props.worker.name = nameInput[0];
			props.worker.phone = phoneInput[0];
		}
	}, [edited, nameInput[0], phoneInput[0]]);

	return <tr>
		<td><StringEdit placeholder="Navn" state={nameInput} save={save} /></td>
		<td><StringEdit placeholder="Telefon" state={phoneInput} save={save} /></td>
		<td><StringEdit placeholder="Note" state={noteInput} save={save} /></td>
		<td>
			<input type="checkbox" checked={activeInput[0]} onChange={(e) => activeInput[1](e.target.checked)} />
		</td>
		<td><a href={loginUrl}>Login</a></td>
		<td><input type="button" value="Gem" onClick={() => save()} disabled={!edited} /></td>
	</tr>;
}

const Workers: React.FC<{workers: {[idString: string]: Worker}}> = (props) => {
	const workers = Object.values(props.workers)
	.filter((worker) => worker.active);
	return <div>
		<table>
			<tbody>
				{workers.map((worker) => <WorkerEdit worker={worker} key={worker.id} />)}
			</tbody>
		</table>
	</div>;
};

export const WorkersMain: React.FC<{}> = (_props) => {
	const [loaded, setLoaded] = React.useState(false);
	const workers = React.useRef<{[idString: string]: any}>({});
	React.useEffect(
		() => {
			(async () => {
				const res = await window.fetch("/api/v0/worker/");
				const data = await res.json();
				for (const row of data.rows) workers.current[row.id + ""] = row;
				setLoaded(true);
			})();
		},
		[]
	)
	return <>
		<Nav current="workers" />
		{loaded ? <Workers workers={workers.current} /> : "Indlæser..."}
	</>;
}