import * as React from "react";
import { DayOfTheWeek, DaySettings, DAYS_OF_THE_WEEK, fetchPost, Shift, Topbar, useFifo, useReloadableFetchJson, Workplace, WorkplaceSettings, WorkplaceSettingsContext } from "./base";
import { fulldateI18n, parseYmd, toIsoDate, weekdayI18n, WEEKDAY_I18N } from "./dateutil";
import { reorderList, UncontrolledStringEdit, useReorderableList } from "./utils";

const WeekBox: React.FC = ({children}) => {
	return <div style={{
		background: "rgba(255,255,255,0.5)",
		border: "1px solid #666",
		display: "flex",
		flexDirection: "row",
		margin: "10px",
	}}>{children}</div>
};

const WeekdayBox: React.FC = ({children}) => {
	return <div style={{
		flex: "0 1 200px"
	}}>{children}</div>
};

const useOnBeforeUnload = (enabled: boolean) => {
	React.useEffect(() => {
		if (!enabled) {
			return () => {};
		}
		const handler = (ev: BeforeUnloadEvent) => {
			ev.preventDefault();
		};
		window.addEventListener("beforeunload", handler);
		return () => {window.removeEventListener("beforeunload", handler);};
	}, [enabled]);
};

const WeekdayDefaultEdit2: React.FC<{
	day: DayOfTheWeek,
	dayName: string,
	value: DaySettings,
	onSave: (day: DayOfTheWeek, value: DaySettings) => Promise<void>,
}> = ({day, dayName, value, onSave}) => {
	const dd = useReorderableList((i, j) => {
		const newShifts = reorderList(value.shifts, i, j);
		console.log({old: value.shifts, i, j, newShifts});
		if (value.shifts !== newShifts) {
			onSave(day, {...value, shifts: newShifts});
		}
	});
	const [editing, setEditing] = React.useState<number | null>(null);
	const inputRef = React.useRef<HTMLInputElement | null>(null);
	React.useLayoutEffect(() => {
		if (editing != null && inputRef.current != null)
		inputRef.current.focus();
	}, [editing])
	return <WeekdayBox>
		<ul>
			<li style={{listStyleType: "none"}}><b>{dayName}</b></li>
			{value.shifts.map((s, i) =>
				<li
					key={i}
					style={dd.isDragging(i) ? {borderTop: "3px solid green", marginTop: "-3px"} : {}}
					onDragLeave={dd.onDragLeave(i)}
					onDragEnter={dd.onDragEnter(i)}
					onDragOver={dd.onDragOver(i)}
					onDrop={dd.onDrop(i)}
				>
					{editing === i ? <UncontrolledStringEdit
						value={s}
						onSave={async (s) => {
							await onSave(day, {
								...value,
								shifts: [
									...value.shifts.slice(0, i),
									s,
									...value.shifts.slice(i + 1),
								],
							});
							setEditing(null);
						}}
						onCancel={() => setEditing(null)}
						inputRef={inputRef}
						/> : <>
						<span
							draggable={editing == null ? "true" : undefined}
							onDragStart={dd.onDragStart(i)}
							onDragEnd={dd.onDragEnd(i)}
							onDoubleClick={() => setEditing(i)}>{s}</span>
							{" "}
							<a href="#" onClick={(e) => {
								e.preventDefault();
								setEditing(null);
								onSave(day, {
									...value,
									shifts: [
										...value.shifts.slice(0, i),
										...value.shifts.slice(i + 1),
									]
								})
							}}>&times;</a>
						</>}
				</li>
			)}
			<li
				style={{
					listStyleType: "none",
					...(dd.isDragging(value.shifts.length) ?
					{borderTop: "3px solid green", marginTop: "-3px"} : {})
				}}
				onDragLeave={dd.onDragLeave(value.shifts.length)}
				onDragEnter={dd.onDragEnter(value.shifts.length)}
				onDragOver={dd.onDragOver(value.shifts.length)}
				onDrop={dd.onDrop(value.shifts.length)}>
				{
					editing === value.shifts.length ?
					<UncontrolledStringEdit
						value={""}
						onSave={async (s) => {
							if (s)
								await onSave(day, {
									...value,
									shifts: [
										...value.shifts,
										s,
									],
								});
							setEditing(null);
						}}
						onCancel={() => setEditing(null)}
						inputRef={inputRef}
						/> : <a href="#" onClick={(e) => {e.preventDefault(); setEditing(value.shifts.length)}}>Tilføj</a>
				}
			</li>
		</ul>
	</WeekdayBox>;
}

const WeekdayDefaultEdit: React.FC<{
	value: WorkplaceSettings,
	save: (w: WorkplaceSettings) => Promise<void>,
}> = ({value, save}) => {
	const days = value.weekday_defaults || {};
	const onSave = React.useCallback(
		(day, shifts) => save({...value, weekday_defaults: {...days, [day]: shifts}}),
		[value],
	);
	return <WeekBox>
		{DAYS_OF_THE_WEEK.map((d, i) => {
			const day = days[d];
			if (day == null) return;
			return <WeekdayDefaultEdit2
				key={d}
				day={d}
				dayName={WEEKDAY_I18N[i]}
				value={day}
				onSave={onSave}
				/>
		})}
	</WeekBox>;
};

const WeekdayDefaultEdit3: React.FC<{
	outer: WorkplaceSettings,
	save: (w: WorkplaceSettings) => Promise<void>,
}> = ({outer, save}) => {
	const [[inner, modified, saving], update] = React.useState([outer, false, false]);
	React.useEffect(() => {
		if (!modified && !saving) {
			update([outer, modified, saving]);
		}
	}, [outer, modified, saving]);
	const saveSettings = React.useCallback(async (value: WorkplaceSettings) => {
		if (saving) return;
		update([value, true, false]);
	}, [saving]);
	const actualSave = React.useCallback(async () => {
		if (saving) return;
		update([inner, true, true]);
		await save(inner);
		update([inner, false, false]);
	}, [inner, saving]);
	useOnBeforeUnload(saving || modified);
	return <>
		<input
			type="button"
			value={saving ? "Gemmer..." : "Gem standardopsætning"}
			disabled={saving || !modified}
			onClick={() => actualSave()}
			/>
		<WeekdayDefaultEdit value={inner} save={saveSettings} />
	</>;
};

interface DayShift {
	id?: number;
	name: string;
	workerCount?: number;
}

const ShiftDayEdit: React.FC<{
	date: string,
	shifts: DayShift[],
	onSave: (date: string, dayShifts: DayShift[]) => Promise<void>,
}> = ({date: dateString, shifts, onSave}) => {
	const date = parseYmd(dateString);
	const dd = useReorderableList((i, j) => {
		const newShifts = reorderList(shifts, i, j);
		console.log({old: shifts, i, j, newShifts});
		if (shifts !== newShifts) {
			onSave(dateString, newShifts);
		}
	});
	const [editing, setEditing] = React.useState<number | null>(null);
	const inputRef = React.useRef<HTMLInputElement | null>(null);
	React.useLayoutEffect(() => {
		if (editing != null && inputRef.current != null)
		inputRef.current.focus();
	}, [editing]);
	const defaults = React.useContext(WorkplaceSettingsContext).weekday_defaults || {};
	const weekday = DAYS_OF_THE_WEEK[(date.getDay() + 6) % 7];
	const defaultEmpty = ((defaults[weekday] || {}).shifts || []).length === 0;
	return <WeekdayBox>
		<ul>
			<li style={{listStyleType: "none"}}><b>{weekdayI18n(date)}</b></li>
			<li style={{listStyleType: "none"}}><b>{fulldateI18n(date)}</b></li>
			{shifts.map((s, i) =>
				<li
					key={i}
					style={dd.isDragging(i) ? {borderTop: "3px solid green", marginTop: "-3px"} : {}}
					onDragLeave={dd.onDragLeave(i)}
					onDragEnter={dd.onDragEnter(i)}
					onDragOver={dd.onDragOver(i)}
					onDrop={dd.onDrop(i)}
				>
					{editing === i ? <UncontrolledStringEdit
						value={s.name}
						onSave={async (name) => {
							await onSave(dateString, [
								...shifts.slice(0, i),
								{...s, name},
								...shifts.slice(i + 1),
							]);
							setEditing(null);
						}}
						onCancel={() => setEditing(null)}
						inputRef={inputRef}
						/> : <>
						<span
							draggable={editing == null ? "true" : undefined}
							onDragStart={dd.onDragStart(i)}
							onDragEnd={dd.onDragEnd(i)}
							onDoubleClick={() => setEditing(i)}>{s.name}</span>
							{" "}
							{s.workerCount != null && `(${s.workerCount} vagttagere) `}
							{!s.workerCount && (shifts.length > 1 || defaultEmpty) && <a href="#" onClick={(e) => {
								e.preventDefault();
								setEditing(null);
								onSave(dateString, [
									...shifts.slice(0, i),
									...shifts.slice(i + 1),
								])
							}}>&times;</a>}
						</>}
				</li>
			)}
			<li
				style={{
					listStyleType: "none",
					...(dd.isDragging(shifts.length) ?
					{borderTop: "3px solid green", marginTop: "-3px"} : {})
				}}
				onDragLeave={dd.onDragLeave(shifts.length)}
				onDragEnter={dd.onDragEnter(shifts.length)}
				onDragOver={dd.onDragOver(shifts.length)}
				onDrop={dd.onDrop(shifts.length)}>
				{
					editing === shifts.length ?
					<UncontrolledStringEdit
						value={""}
						onSave={async (s) => {
							if (s)
								await onSave(dateString, [
									...shifts,
									{name: s},
								]);
							setEditing(null);
						}}
						onCancel={() => setEditing(null)}
						inputRef={inputRef}
						/> : <a href="#" onClick={(e) => {e.preventDefault(); setEditing(shifts.length)}}>Tilføj</a>
				}
			</li>
		</ul>
	</WeekdayBox>;
};

const ShiftWeekEdit: React.FC<{
	days: {
		date: string;
		shifts: DayShift[];
	}[],
	onSave: (date: string, dayShifts: DayShift[]) => Promise<void>,
}> = ({days, onSave}) => {
	const containers = [];
	for (const day of days) {
		containers.push(
			<ShiftDayEdit
				key={day.date}
				date={day.date}
				shifts={day.shifts}
				onSave={onSave}
				/>
		);
	}
	return <WeekBox>
		{containers}
	</WeekBox>;
};

const getMonday = (date: Date) => {
	const monday = new Date(date);
	monday.setDate(monday.getDate() - (monday.getDay() + 6) % 7);
	return monday;
};

const ShiftEdit: React.FC<{
	shifts: Shift[],
	onSave: (modifiedDays: {[date: string]: DayShift[]}) => Promise<void>,
}> = ({shifts, onSave}) => {
	const [[modifiedDays, saving], update] = React.useState([{} as {[date: string]: DayShift[]}, false]);
	const modifiedDayCount = Object.keys(modifiedDays).length;
	const modified = modifiedDayCount > 0;

	const saveInner = React.useCallback(async (date, dayShifts) => {
		update(([modifiedDays, saving]) => [saving ? modifiedDays : {...modifiedDays, [date]: dayShifts}, saving]);
	}, []);
	const saveOuter = React.useCallback(() => {
		update(([modifiedDays, saving]) => {
			if (saving) return [modifiedDays, true];
			onSave(modifiedDays).then(() => update([{}, false]));
			return [modifiedDays, true];
		});
	}, [])

	const weeks: {
		monday: string;
		days: {
			date: string;
			shifts: DayShift[];
		}[];
	}[] = [];
	for (const s of shifts) {
		const {id, name, workers, date} = s;
		const dayShift = {id, name, workerCount: workers.length};
		const monday = toIsoDate(getMonday(parseYmd(date)));
		{
			const currentWeek = weeks[weeks.length - 1];
			if (currentWeek == null || currentWeek.monday !== monday) {
				weeks.push({monday, days: []});
			}
		}
		const currentWeek = weeks[weeks.length - 1];
		const currentDay = currentWeek.days[currentWeek.days.length - 1];
		if (currentDay == null || currentDay.date !== date) {
			currentWeek.days.push({date, shifts: []});
		}
		currentWeek.days[currentWeek.days.length - 1].shifts.push(dayShift);
	}
	for (const week of weeks) {
		for (let i = 0; i < week.days.length; ++i) {
			const m = modifiedDays[week.days[i].date];
			if (m != null) week.days[i].shifts = m;
		}
	}
	const containers = [];
	for (const week of weeks) {
		containers.push(
			<ShiftWeekEdit
				key={week.monday}
				days={week.days}
				onSave={saveInner}
				/>
		)
	}
	useOnBeforeUnload(saving || modified);
	return <div>
		<input
			type="button"
			value={saving ? "Gemmer..." : `Gem ${modifiedDayCount} ændrede dage`}
			disabled={saving || !modified}
			onClick={() => saveOuter()}
			/>
		{containers}
	</div>;
};

export const ShiftsMain: React.FC<{}> = (_props) => {
	const [fromdate] = React.useState(toIsoDate(getMonday(new Date())));
	const [initialLoaded, enqueueInitial] = useFifo();
	const [_, enqueue] = useFifo();
	const [workplaceJson, reloadWorkplace] = useReloadableFetchJson<{rows: Workplace[]}>();
	const [shiftsJson, reloadShifts] = useReloadableFetchJson<{rows: Shift[]}>();
	const workplaceSettings = (workplaceJson == null || !workplaceJson.rows) ? {} : workplaceJson.rows[0].settings;
	React.useEffect(
		() => {
			enqueueInitial(() => reloadWorkplace(window.fetch("/api/v0/workplace/")));
			enqueueInitial(() => reloadShifts(window.fetch("/api/v0/shift/?fromdate=" + fromdate)));
		},
		[],
	);
	const saveDefaults = React.useCallback(
		(workplaceSettings: WorkplaceSettings) => new Promise<void>((resolve) => {
			enqueue(async () => {
				if (workplaceJson != null) {
					const res = await fetchPost("/api/v0/workplace/", {...workplaceJson.rows[0], settings: workplaceSettings});
					if (res.ok) {
						await reloadWorkplace(window.fetch("/api/v0/workplace/"));
					}
				}
				resolve();
			});
		}),
		[workplaceJson],
	);
	const saveShifts = React.useCallback(
		(modifiedDays: {[dayString: string]: DayShift[]}) => new Promise<void>((resolve) => {
			enqueue(async () => {
				const res = await fetchPost("/api/v0/shift/", {modifiedDays});
				if (res.ok) {
					await reloadShifts(window.fetch("/api/v0/shift/?fromdate=" + fromdate));
				}
				resolve();
			});
		}),
		[fromdate],
	)
	return <>
		<Topbar current="shifts" />
		{!initialLoaded ? "Indlæser..." : <div>
			<p><b>Træk og slip</b> for at ændre rækkefølgen af vagter.</p>
			<p><b>Dobbeltklik</b> på en vagts navn for at ændre navnet.</p>
			<WeekdayDefaultEdit3 outer={workplaceSettings} save={saveDefaults} />
			<WorkplaceSettingsContext.Provider value={workplaceSettings}>
				<ShiftEdit shifts={(shiftsJson || {}).rows || []} onSave={saveShifts} />
			</WorkplaceSettingsContext.Provider>
		</div>}
	</>;
}
