import * as React from "react";

export interface WorkerStatsEntry {
	isoyear: number;
	isoweek: number;
	year: number;
	month: number;
	count: number;
}

export interface WorkerStatsRow {
	id: number;
	name: string;
	active: boolean;
	stats: WorkerStatsEntry[];
}

export function useApiWorkerStats() {
	const [data, setData] = React.useState<WorkerStatsRow[] | null>(null);
	React.useEffect(() => {
		fetch("/api/v0/worker_stats/").then((r) => r.json()).then((o) => setData(o.workers));
	}, []);
    return data;
}

export interface AggregatedEntry {
	name: string;
	count: number;
}

export const aggregateEntriesBy = (fun: (entry: WorkerStatsEntry) => string, entries: WorkerStatsEntry[]) => {
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
