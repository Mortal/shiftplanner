import * as React from "react";
import { fetchPost, Topbar, Worker } from "./base";

interface Workers {
	loadCount: number;
	workers: {[id: string]: Worker};
}

const WorkerListContext = React.createContext<{[id: string]: Worker}>({});
const RefreshTheWorldContext = React.createContext<
	<T extends unknown>(prepare: (done: (doRefresh: boolean) => Promise<void>) => Promise<T>) => Promise<T>
>((prepare) => prepare(async (_doRefresh) => {}));

const TextSelect: React.FC<{options: {value: string, label: string}[], onCancel: () => void, onSubmit: (value: string) => void}> = (props) => {
	const [value, setValue] = React.useState("");
	const [selectedIndex, setSelectedIndex] = React.useState(0);
	const [focused, setFocused] = React.useState(true);
	const [hover, setHover] = React.useState(false);
	const inputRef = React.useRef<HTMLInputElement | null>(null);
	React.useLayoutEffect(() => {if (inputRef.current) inputRef.current.focus();}, []);
	const onInputChange = (v: string) => {
		setValue(v);
		setSelectedIndex(0);
	};
	const valueTrim = value.trim().toLowerCase();
	const filteredOptions = React.useMemo(
		() => props.options.filter(({label}) => valueTrim === "" || label.toLowerCase().indexOf(valueTrim) >= 0),
		[valueTrim]
	);
	const onKeyDown = React.useCallback((code: string) => {
		if (code === "Enter" && filteredOptions.length > selectedIndex)
			props.onSubmit(filteredOptions[selectedIndex].value);
		else if (code === "Escape") props.onCancel();
		else if (code === "ArrowDown") setSelectedIndex((selectedIndex) => Math.min(selectedIndex + 1, filteredOptions.length - 1));
		else if (code === "ArrowUp") setSelectedIndex((selectedIndex) => Math.max(0, selectedIndex - 1));
	}, [valueTrim, selectedIndex]);
	return <>
	<div style={{display: "inline-block"}}>
	<input
		style={{display: "block"}}
		ref={inputRef}
		value={value}
		onKeyDown={(e) => onKeyDown(e.code)}
		onChange={(e) => onInputChange(e.target.value)}
		onFocus={() => setFocused(true)}
		onBlur={() => setFocused(false)} />
	{(focused || hover) &&
	<ul
		onMouseEnter={() => setHover(true)}
		onMouseLeave={() => setHover(false)}
		style={{
			position: "absolute",
			background: "white",
			border: "1px solid black",
			overflow: "auto",
			width: "200px",
			height: "200px",
		}}
	>
		{filteredOptions
		.map(({value, label}, i) =>
		<li key={value}>
			<a href="#" onClick={(e) => {e.preventDefault(); props.onSubmit(value);}} style={{fontWeight: i === selectedIndex ? "bold" : undefined}}>
				{label}
			</a>
		</li>
		)}
	</ul>
	}
	</div>
	</>
}

const useReorderableList = (onReorder: (i: number, j: number) => void) => {
	const [currentDropTarget, setCurrentDropTarget] = React.useState<number | null>(null);
	const [dragging, setDragging] = React.useState<number | null>(null);
	return {
		onDragLeave: (i: number) =>
			(_e: React.DragEvent) =>
				setCurrentDropTarget((v) => v === i ? null : v),
		onDragEnter: (i: number) =>
			(_e: React.DragEvent) => setCurrentDropTarget(i),
		onDragOver: (_i: number) =>
			(e: React.DragEvent) => {if (dragging != null) e.preventDefault();},
		onDrop: (i: number) =>
			(e: React.DragEvent) => {
				if (dragging == null || currentDropTarget !== i) return;
				e.preventDefault();
				onReorder(dragging, currentDropTarget);
			},
		isDragging: (i: number) => (dragging != null && currentDropTarget === i),
		onDragStart: (i: number) => (_e: React.DragEvent) => setDragging(i),
		onDragEnd: (i: number) => (_e: React.DragEvent) => setDragging((v) => v === i ? null : v),
	}
};

const ShiftEdit: React.FC<{row: any, showTimes?: boolean}> = (props) => {
	const { row } = props;
	const [addShown, setAddShown] = React.useState("hidden");
	const refreshTheWorld = React.useContext(RefreshTheWorldContext);

	const setWorkers = (workers: Worker[]) => refreshTheWorld(
		async (done) => {
			const body = {workers};
			const res = await fetchPost(
				`/api/v0/shift/${row.date}/${row.slug}/`,
				body,
			);
			done(res.ok);
			return res;
		}
	);

	const dd = useReorderableList(
		(dragging, currentDropTarget) => {
			if (dragging === currentDropTarget || dragging + 1 === currentDropTarget) return;
			const newWorkers = [...row.workers];
			newWorkers.splice(dragging, 1);
			newWorkers.splice(currentDropTarget < dragging ? currentDropTarget : (currentDropTarget - 1), 0, row.workers[dragging]);
			setWorkers(newWorkers);
		}
	);

	const addWorker = async (worker: Worker) => {
		setAddShown("loading");
		const res = await setWorkers([...row.workers, worker]);
		if (!res.ok) {
			console.log(`HTTP ${res.status} when adding worker`);
		}
		setAddShown("show");
	};

	const removeWorker = async (idx: number) => {
		const newWorkers: any[] = row.workers.slice();
		newWorkers.splice(idx, 1);
		const res = await setWorkers(newWorkers);
		if (!res.ok) {
			console.log(`HTTP ${res.status} when adding worker`);
		}
	};

	const ex: {[workerId: string]: true} = {};
	for (const w of row.workers) ex[w.id + ""] = true;
	return <div className="sp_shift">
		<h2>{ row.name }</h2>
		{props.showTimes && <><p>Tilmelding åbner: {row.settings.registration_starts}</p>
		<p>Tilmelding lukker: {row.settings.registration_deadline}</p></>}
		<ol>
			{row.workers.map(
				({name}: {name: string}, i: number) =>
				<li
					key={i}
					style={dd.isDragging(i) ? {borderTop: "3px solid green", marginTop: "-3px"} : {}}
					onDragLeave={dd.onDragLeave(i)}
					onDragEnter={dd.onDragEnter(i)}
					onDragOver={dd.onDragOver(i)}
					onDrop={dd.onDrop(i)}
				>
					<span
						draggable
						onDragStart={dd.onDragStart(i)}
						onDragEnd={dd.onDragEnd(i)}
					>{name}</span>
					{" "}
					<a href="#" onClick={(e) => {e.preventDefault(); removeWorker(i)}}>
						&times;
					</a>
				</li>
			)}
			<li
				style={{
					listStyle: "none",
					...(dd.isDragging(row.workers.length) ? {borderTop: "3px solid green", marginTop: "-3px"} : {})
				}}
				onDragLeave={dd.onDragLeave(row.workers.length)}
				onDragEnter={dd.onDragEnter(row.workers.length)}
				onDragOver={dd.onDragOver(row.workers.length)}
				onDrop={dd.onDrop(row.workers.length)}
			>
				{addShown === "hidden"
				? <a href="#" onClick={(e) => {e.preventDefault(); setAddShown("show")}}>Tilføj</a>
				: <WorkerListContext.Consumer>
					{(workers) => 
					<TextSelect key={row.workers.length + "add"} options={Object.entries(workers)
						.filter(([id, worker]) => worker.active && !((id + "") in ex))
						.map(([id, worker]) => ({value: id + "", label: worker.name}))}
						onCancel={() => setAddShown("hidden")}
						onSubmit={(v) => addWorker(workers[v])} />}
				</WorkerListContext.Consumer>}
			</li>
		</ol>
	</div>;
}

const DayEdit: React.FC<{date: string, rows: any[], showTimes?: boolean}> = (props) => {
	const { date, rows } = props;
	const [y, m, d] = date.split("-").map((v) => parseInt(v));
	const DAYS_OF_THE_WEEK = ["søndag", "mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag"];
	const MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"]
	const dateObject = new Date(y, m - 1, d);
	return <div className="sp_weekday_shifts">
		<h1>
			<div className="sp_the_weekday">{DAYS_OF_THE_WEEK[dateObject.getDay()]}</div>
			<div className="sp_the_fulldate">{dateObject.getDate()}. {MONTHS[dateObject.getMonth()]} {dateObject.getFullYear()}</div>
		</h1>
		{rows.map((row) => <ShiftEdit key={row.order} row={row} showTimes={props.showTimes} />)}
	</div>;
}

function allSame(xs: any[]): boolean {
	for (const x of xs) if (x !== xs[0]) return false;
	return true;
}

const ScheduleEdit: React.FC<{data: any[]}> = (props) => {
	const { data } = props;
	const dataByDate: {[date: string]: any[]} = {};
	for (const row of data) {
		(dataByDate[row.date] || (dataByDate[row.date] = [])).push(row);
	}
	const allTimesSame =
		allSame(data.map((row) => row.settings.registration_starts)) &&
		allSame(data.map((row) => row.settings.registration_deadline));
	return <>
		{allTimesSame && data.length > 0 &&
		<div>
			Tilmelding åbner: {data[0].settings.registration_starts}
			{" "}Tilmelding lukker: {data[0].settings.registration_deadline}
			{" "}<a href="print/">Print</a>
		</div>}
		<div className="sp_days">
			{Object.entries(dataByDate).map(
				([date, rows]) => (
					<DayEdit key={date} date={date} rows={rows} showTimes={!allTimesSame} />
				)
			)}
		</div>
	</>;
}

function useKeyboardShortcuts(shortcuts: {[key: string]: () => void}) {
	React.useEffect(() => {
		const onkeypress = (e: KeyboardEvent) => {
			if ((e.target as any).tagName === "INPUT") return;
			if (e.code in shortcuts) shortcuts[e.code]();
			else return;
			e.preventDefault();
		};
		window.addEventListener("keypress", onkeypress, false);
		return () => window.removeEventListener("keypress", onkeypress, false);
	});
}

function useDelayFalse(current: boolean, delay: number) {
	const [value, setValue] = React.useState(current);
	React.useEffect(() => {
		if (!current && value) {
			const to = setTimeout(() => setValue(false), delay);
			return () => void(clearTimeout(to));
		}
		if (current && !value) {
			setValue(true);
		}
		return () => {};
	}, [current, value]);
	return value;
}

export const ScheduleEditMain: React.FC<{week?: number, year?: number}> = (props) => {
	const [error, setError] = React.useState("");

	const [refreshCount, setRefreshCount] = React.useState(0);
	const [loading, setLoading] = React.useState(false);
	const [weekYear, setWeekYear] = React.useState({week: 0, year: 0, refreshCount});
	const [weekYearLoading, setWeekYearLoading] = React.useState({week: props.week || 1, year: props.year || 2022, relative: 0});
	const loaded =
		!loading &&
		weekYear.week === weekYearLoading.week + weekYearLoading.relative &&
		weekYear.year === weekYearLoading.year &&
		weekYear.refreshCount === refreshCount;
	const {week, year, relative} = weekYearLoading;
	const data = React.useRef<any[]>([]);
	const nextMap = React.useRef<{[yw: string]: string}>({});
	const prevMap = React.useRef<{[yw: string]: string}>({});

	const workers = React.useRef<Workers>({loadCount: 0, workers: {}});
	React.useEffect(() => {
		(async () => {
			const res = await window.fetch("/api/v0/worker/");
			const data = await res.json();
			for (const row of data.rows) workers.current.workers[row.id + ""] = row;
			workers.current.loadCount += 1;
		})();
	}, []);

	const loadHelper = React.useCallback(
		async (year: number, week: number) => {
			const res = await window.fetch(`/api/v0/shift/?week=${year}w${week}`);
			if (!res.ok) {
				return {ok: false, status: res.status}; 
			}
			const theData = await res.json();
			console.log({next: theData.next, prev: theData.prev})
			nextMap.current[`${year}w${week}`] = theData["next"];
			prevMap.current[`${year}w${week}`] = theData["prev"];
			return {ok: true, status: res.status, rows: theData.rows};
		},
		[]
	);

	React.useEffect(() => {
		if (loaded) return;
		let stop = false;
		(async () => {
			let w = week;
			let y = year;
			let r = relative;
			let theData = null;
			while (r !== 0) {
				if (stop) return;
				if (!nextMap.current[`${y}w${w}`]) {
					const res = await loadHelper(y, w);
					if (!res.ok) {
						setError(`HTTP ${res.status}`);
						return;
					}
					theData = res.rows;
				}
				if (r > 0) {
					[y, w] = nextMap.current[`${y}w${w}`].split("w").map((v) => parseInt(v));
					r -= 1;
				} else {
					[y, w] = prevMap.current[`${y}w${w}`].split("w").map((v) => parseInt(v));
					r += 1;
				}
			}
			if (theData == null) {
				if (stop) return;
				const res = await loadHelper(y, w);
				if (!res.ok) {
					setError(`HTTP ${res.status}`);
					return;
				}
				theData = res.rows;
			}
			data.current.splice(0, data.current.length, ...theData);
			setWeekYear({week: w, year: y, refreshCount});
			window.history.replaceState({}, document.title, `/admin/s/${y}w${w}/`);
			setWeekYearLoading({week: w, year: y, relative: 0});
		})();
		return () => {stop = true};
	}, [week, year, relative, refreshCount]);

	const loadPrev = React.useCallback(
		() => {
			setWeekYearLoading(
				({week, year, relative}) => ({week, year, relative: relative - 1})
			)
		},
		[]
	);
	const loadNext = React.useCallback(
		() => {
			setWeekYearLoading(
				({week, year, relative}) => ({week, year, relative: relative + 1})
			)
		},
		[]
	);
	const onRefresh: <T extends unknown>(prepare: (done: (doRefresh: boolean) => Promise<void>) => Promise<T>) => Promise<T> = React.useCallback(
		async (prepare) => {
			// console.log("Prep...");
			setLoading(true);
			// await new Promise((r) => setTimeout(r, 1000));
			return await prepare(
				async (doRefresh) => {
					// console.log("Prepped...");
					// await new Promise((r) => setTimeout(r, 1000));
					if (doRefresh) setRefreshCount((refreshCount) => refreshCount + 1);
					setLoading(false);
					// console.log("Done...");
				}
			)
		},
		[]
	);

	useKeyboardShortcuts({
		KeyJ: loadNext,
		KeyK: loadPrev,
	});

	const fadeWhileLoading = !useDelayFalse(loaded, 500);

	return <WorkerListContext.Provider value={workers.current.workers}>
		<Topbar current="schedule" />
		{error !== "" && <div className="sp_error">{error}</div>}
		<div className="sp_weekheader">
			<div className="sp_prev"><a href="#" onClick={e => {e.preventDefault(); loadPrev()}}>&larr;</a></div>
			<div className="sp_weekdisplay">Uge { week }, { year }</div>
			<div className="sp_next"><a href="#" onClick={e => {e.preventDefault(); loadNext()}}>&rarr;</a></div>
		</div>
		<div style={{opacity: fadeWhileLoading ? 0.7 : undefined}}>
			<RefreshTheWorldContext.Provider value={onRefresh}>
				<ScheduleEdit data={data.current} />
			</RefreshTheWorldContext.Provider>
		</div>
	</WorkerListContext.Provider>;
}
