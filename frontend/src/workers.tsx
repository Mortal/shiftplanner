import * as React from "react";
import { fetchPost, Worker } from "./base";

const WorkerEdit: React.FC<{worker: Worker}> = (props) => {
	const {id, name, phone, login_secret: loginSecret} = props.worker;
	const loginUrl = `/login/?` + new URLSearchParams({phone, password: loginSecret});
	const [nameInput, setNameInput] = React.useState(name);
	const [phoneInput, setPhoneInput] = React.useState(phone);
	const edited = nameInput !== name || phoneInput !== phone;

	const save = React.useCallback(async () => {
		if (!edited) return;
		const res = await fetchPost(`/api/v0/worker/${id}/`, {name: nameInput, phone: phoneInput});
		if (res.ok) {
			props.worker.name = nameInput;
			props.worker.phone = phoneInput;
		}
	}, [edited, nameInput, phoneInput]);

	const onKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.code !== "Enter") return;
		e.preventDefault();
		save();
	};

	return <tr>
		<td><input value={nameInput} onChange={(e) => setNameInput(e.target.value)} onKeyPress={onKeyPress} /></td>
		<td><input value={phoneInput} onChange={(e) => setPhoneInput(e.target.value)} onKeyPress={onKeyPress} /></td>
		<td><a href={loginUrl}>Login</a></td>
		<td><input type="button" value="Gem" onClick={() => save()} disabled={!edited} /></td>
	</tr>;
}

const Workers: React.FC<{workers: {[idString: string]: Worker}}> = (props) => {
	return <div>
		<table>
			<tbody>
				{Object.values(props.workers).map((worker) => <WorkerEdit worker={worker} key={worker.id} />)}
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
	return loaded ? <Workers workers={workers.current} /> : <>Indlæser...</>;
}