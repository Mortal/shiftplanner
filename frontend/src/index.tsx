import * as React from "react";
import * as ReactDOM from "react-dom";
import { ChangelogMain } from "./changelog";
import { ScheduleEditMain } from "./schedule";
import { SettingsMain } from "./settings";
import { WorkersMain } from "./workers";
import { WorkerStatsMain } from "./worker_stats";
import { ShiftsMain } from "./shifts";

type ShiftPlannerViewProps =
	{view: "schedule", week: number, year: number}
	| {view: "workers" | "settings" | "workerStats" | "changelog" | "shifts"};

const ShiftPlannerView: React.FC<ShiftPlannerViewProps> = (props) => {
	const {view} = props;
	switch (view) {
		case "schedule": {
			const {week, year} = props;
			return <ScheduleEditMain week={week} year={year} />;
		}
		case "workers":
			return <WorkersMain />;
		case "settings":
			return <SettingsMain />;
		case "workerStats":
			return <WorkerStatsMain />;
		case "changelog":
			return <ChangelogMain />;
		case "shifts":
			return <ShiftsMain />;
	}
}

ReactDOM.render(<ShiftPlannerView {...(window as any).shiftplannerOptions} />, document.getElementById("shiftplanner_admin"));
