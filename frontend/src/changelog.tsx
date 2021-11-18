import * as React from "react";
import { Topbar, useFifo, useReloadableFetchJson, useRowsToIdMap, Worker, WorkerListContext } from "./base";

const WorkerListContextProvider: React.FC<{enqueue: (work: () => Promise<void>) => void}> = (props) => {
	const [workersJson, reloadWorkers] =
		useReloadableFetchJson<{rows: Worker[]}>(props.enqueue);
	React.useEffect(() => reloadWorkers(window.fetch("/api/v0/worker/")), []);
	const workers = useRowsToIdMap(workersJson);
	return <WorkerListContext.Provider value={workers}>
		{props.children}
	</WorkerListContext.Provider>;
};

const useSelectWorker = (loaded: boolean) => {
	const [worker, setWorker] = React.useState<Worker | null>(null);
	const workers = React.useContext(WorkerListContext);
	const workerList = [...Object.values(workers)];
	const workerDropdown = <select value={worker == null ? 0 : worker.id} onChange={
		(e) => setWorker(
			e.target.selectedIndex === 0 ? null :
			workerList[e.target.selectedIndex - 1]
		)
	}>
		<option value={0}>{(workerList.length === 0 && !loaded) ? "Loading..." : "---"}</option>
		{workerList.map(
			(worker, i) =>
			<option value={worker.id} key={i}>{worker.name}</option>
		)}
	</select>;
	return [worker, workerDropdown] as [Worker, typeof workerDropdown];
};

interface Changelog {
	time: number;
	worker_id: number;
	user_id: number;
	kind: string;
	data: {[k: string]: any};
};

const KINDS = {
	register: "Tilmeld",
	unregister: "Afmeld",
	worker_login: "Log ind",
	comment: "Bemærkning",
	edit_worker: "(Admin) Redigér vagttager",
	edit: "(Admin) Redigér vagtplan",
	import_workers: "(Admin) Importér vagttagere",
	edit_workplace_settings: "(Admin) Redigér indstillinger",
}

const ChangelogRow: React.FC<{data: Changelog}> = (props) => {
	const workers = React.useContext(WorkerListContext);
	const {data: {time, worker_id, user_id, kind, data}} = props;
	const dt = new Date(time * 1000);
	const dataCopy = {...data};
	if (workers[dataCopy.worker]) dataCopy.worker = workers[dataCopy.worker].name;
	if (kind === "edit_worker" && workers[dataCopy.id]) dataCopy.id = workers[dataCopy.id].name;
	const dataString = JSON.stringify(dataCopy) + "";
	return <tr>
		<td>{dt + ""}</td>
		<td>{worker_id == null ? "-" : workers[worker_id] ? workers[worker_id].name : worker_id + ""}</td>
		<td>{user_id == null ? "-" : user_id + ""}</td>
		<td>{KINDS[kind] || kind}</td>
		<td title={dataString}>{dataString.substring(0, 50)}</td>
	</tr>
};

const useChangelog = (worker: Worker | null) => {
	const [loaded, enqueue] = useFifo();
	const [changelogJson, reload] = useReloadableFetchJson<{rows: Changelog[]}>(enqueue);
	React.useEffect(() => {
		let url = "/api/v0/changelog/";
		if (worker != null) url += "?" + new URLSearchParams({worker: worker.id + ""});
		reload(window.fetch(url));
	}, [worker]);
	const changelogRows = changelogJson == null ? [] : changelogJson.rows;
	return loaded ? <table>
		<tbody>
			{changelogRows.slice(0, 1000).map((e, i) => <ChangelogRow key={i} data={e} />)}
		</tbody>
	</table> : <>Loading...</>;
};

const Changelog: React.FC<{loaded: boolean}> = (props) => {
	const [worker, workerDropdown] = useSelectWorker(props.loaded);
	const changelog = useChangelog(worker);
	return <>
		{workerDropdown}
		{changelog}
	</>;
};

export const ChangelogMain: React.FC<{}> = (_props) => {
	const [loaded, enqueue] = useFifo();
	return <WorkerListContextProvider enqueue={enqueue}>
		<Topbar current="changelog" />
		<Changelog loaded={loaded} />
	</WorkerListContextProvider>;
};
