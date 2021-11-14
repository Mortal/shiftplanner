import * as React from "react";
import * as ReactDOM from "react-dom";
import { ChangelogMain } from "./changelog";
import { ScheduleEditMain } from "./schedule";
import { SettingsMain } from "./settings";
import { WorkersMain } from "./workers";
import { WorkerStatsMain } from "./worker_stats";

(window as any).initScheduleEdit = (root: HTMLDivElement, options?: {week?: number, year?: number}) => {
	const {week, year} = options || {};
	ReactDOM.render(<ScheduleEditMain week={week} year={year} />, root);
};

(window as any).initWorkers = (root: HTMLDivElement, options?: {}) => {
	const {} = options || {};
	ReactDOM.render(<WorkersMain />, root);
};

(window as any).initSettings = (root: HTMLDivElement, options?: {}) => {
	const {} = options || {};
	ReactDOM.render(<SettingsMain />, root);
};

(window as any).initWorkerStats = (root: HTMLDivElement, options?: {}) => {
	const {} = options || {};
	ReactDOM.render(<WorkerStatsMain />, root);
};

(window as any).initChangelog = (root: HTMLDivElement, options?: {}) => {
	const {} = options || {};
	ReactDOM.render(<ChangelogMain />, root);
};
