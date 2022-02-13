import * as React from "react";
import { fetchPost, Topbar, useFifo, useReloadableFetchJson, useRowsToIdMap, Worker, Workplace, WorkplaceSettings, WorkplaceSettingsContext } from "./base";
import { StringEdit, useEditables } from "./utils";

export const ShiftsMain: React.FC<{}> = (_props) => {
	const [loaded, enqueue] = useFifo();
	const [workersJson, reloadWorkersInner] = useReloadableFetchJson<{rows: Worker[]}>(enqueue);
	const reloadWorkers =
		React.useCallback(() => reloadWorkersInner(window.fetch("/api/v0/worker/")), []);
	const workers = useRowsToIdMap<Worker>(workersJson);
	const [workplaceJson, reloadWorkplace] = useReloadableFetchJson<{rows: Workplace[]}>(enqueue);
	const workplaceSettings = (workplaceJson == null || !workplaceJson.rows) ? {} : workplaceJson.rows[0].settings;
	React.useEffect(
		() => {
			reloadWorkers();
			reloadWorkplace(window.fetch("/api/v0/workplace/"));
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
	return <>
		<Topbar current="shifts" />
		<div>
			<WorkplaceSettingsContext.Provider value={workplaceSettings}>
				Hello world
			</WorkplaceSettingsContext.Provider>
		</div>
	</>;
}
