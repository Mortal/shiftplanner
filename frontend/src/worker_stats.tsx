import * as React from "react";
import { aggregateEntriesBy, useApiWorkerStats, WorkerStatsRow, WorkerStatsEntry } from "./api";
import { Topbar } from "./base";

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

const WorkerStats: React.FC<{data: WorkerStatsRow[]}> = (props) => {
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
	const data = useApiWorkerStats();
	return <>
		<Topbar current="worker_stats" />
		{data == null ? <>Indlæser...</> : <WorkerStats data={data.filter((d) => d.active)} />}
	</>;
};
