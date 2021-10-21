import * as React from "react";
import { Topbar } from "./base";

interface WorkerStatsEntry {
	isoyear: number;
	isoweek: number;
	year: number;
	month: number;
	count: number;
}

interface AggregatedEntry {
	name: string;
	count: number;
}

interface WorkerStats {
	id: number;
	name: string;
	active: boolean;
	stats: WorkerStatsEntry[];
}

const aggregateEntriesBy = (fun: (entry: WorkerStatsEntry) => string, entries: WorkerStatsEntry[]) => {
	const p: {[k: string]: AggregatedEntry} = {};
	const res = [];
	for (const entry of entries) {
		const k = fun(entry);
		if (!(k in p)) {
			res.push({name: k, count: 0});
			p[k] = res[res.length-1];
		}
		p[k].count += entry.count;
	}
	return res;
};

function leftpad(n: number) {
	const s = "00" + n;
	return s.substring(s.length-2);
}

const aggregateEntries = (division: "month" | "week", entries: WorkerStatsEntry[]) => {
	if (division === "month")
		return aggregateEntriesBy((entry) => `${entry.year}-${leftpad(entry.month)}`, entries);
	else
		return aggregateEntriesBy((entry) => `${entry.isoyear}w${leftpad(entry.isoweek)}`, entries);
};

function useSelectDivision() {
	const [division, setDivision] = React.useState<"month" | "week">("month");
	const options = [
		["month", "Måned"],
		["week", "Uge"],
	]
	const component = <select onChange={(e) => setDivision(e.target.value as any)} value={division}>
		{options.map(([o, label]) => <option key={o} value={o}>{label}</option>)}
	</select>
	return [division, component] as [typeof division, typeof component];
}

const WorkerStats: React.FC<{data: WorkerStats[]}> = (props) => {
	const [division, selectDivision] = useSelectDivision();
	const aggregated = props.data.map(
		(w) => ({
			...w,
			agg: Object.fromEntries(
				aggregateEntries(division, w.stats).map(({name, count}) => [name, count])
			)
		})
	);
	const keyMap: {[k: string]: true} = {};
	for (const {agg} of aggregated) {
		for (const key of Object.keys(agg)) keyMap[key] = true;
	}
	const keys = [...Object.keys(keyMap)];
	keys.sort();
	return <div>
		<div>{selectDivision}</div>
		<table className="sp_worker_stats" cellSpacing={0}>
			<thead>
				<tr>
					<th>Navn</th>
					{keys.map((k) => <th key={k}>{k}</th>)}
				</tr>
			</thead>
			<tbody>
				{aggregated.map(({id, name, agg}) => <tr key={id}>
					<th>{name}</th>
					{keys.map((k) => <td key={k}>{agg[k]}</td>)}
				</tr>)}
			</tbody>
		</table>
	</div>;
};

export const WorkerStatsMain: React.FC<{}> = (_props) => {
	const [data, setData] = React.useState<WorkerStats[] | null>(null);
	React.useEffect(() => {
		fetch("/api/v0/worker_stats/").then((r) => r.json()).then((o) => setData(o.workers));
	}, []);
	return <>
		<Topbar current="worker_stats" />
		{data == null ? <>Indlæser...</> : <WorkerStats data={data.filter((d) => d.active)} />}
	</>;
};
