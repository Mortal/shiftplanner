import * as React from "react";

export interface WorkerStatsEntry {
	isoyear: number;
	isoweek: number;
	year: number;
	month: number;
	count: number;
}

export interface WorkerStats {
	id: number;
	name: string;
	active: boolean;
	stats: WorkerStatsEntry[];
}

export function useApiWorkerStats() {
	const [data, setData] = React.useState<WorkerStats[] | null>(null);
	React.useEffect(() => {
		fetch("/api/v0/worker_stats/").then((r) => r.json()).then((o) => setData(o.workers));
	}, []);
    return data;
}