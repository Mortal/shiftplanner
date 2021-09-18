import * as React from "react";
import * as ReactDOM from "react-dom";
import { Foo } from "./foo";

const ShiftEdit: React.FC<{row: any}> = (props: {row: any}) => {
	const { row } = props;
	return <div className="sp_shift">
		<h2>{ row.name }</h2>
		<ol>
			{row.workers.map(({name}: {name: string}, i: number) => <li key={i}>{name}</li>)}
		</ol>
	</div>;
}

const DayEdit: React.FC<{date: string, rows: any[]}> = (props: {date: string, rows: any[]}) => {
	const { date, rows } = props;
	return <div className="sp_weekday_shifts">
		<h1>
			<div className="sp_the_weekday">blursdag</div>
			<div className="sp_the_fulldate">{date}</div>
		</h1>
		{rows.map((row) => <ShiftEdit key={row.order} row={row} />)}
	</div>;
}

const ScheduleEdit: React.FC<{data: any[]}> = (props: {data: any[]}) => {
	const { data } = props;
	const dataByDate: {[date: string]: any[]} = {};
	for (const row of data) {
		(dataByDate[row.date] || (dataByDate[row.date] = [])).push(row);
	}
	return <>
		{Object.entries(dataByDate).map(
			([date, rows]) => (
				<DayEdit key={date} date={date} rows={rows} />
			)
		)}
	</>;
}

const ScheduleEditMain: React.FC = (_props: {}) => {
	const [error, setError] = React.useState("");

	const [weekYear, setWeekYear] = React.useState({week: 0, year: 0});
	const [weekYearLoading, setWeekYearLoading] = React.useState({week: 1, year: 2022, relative: 0});
	const loaded =
		weekYear.week == weekYearLoading.week + weekYearLoading.relative &&
		weekYear.year == weekYearLoading.year;
	const {week, year, relative} = weekYearLoading;
	const data = React.useRef<any[]>([]);
	const nextMap = React.useRef<{[yw: string]: string}>({});
	const prevMap = React.useRef<{[yw: string]: string}>({});

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
	)

	React.useEffect(() => {
		if (loaded) return;
		console.log("Going to load", {week, year, relative});
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
			setWeekYear({week: w, year: y});
			setWeekYearLoading({week: w, year: y, relative: 0});
		})();
		return () => {stop = true};
	}, [week, year, relative]);

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

	return <>
		{error !== "" && <div className="sp_error">{error}</div>}
		<div className="sp_weekheader">
			<div className="sp_prev"><a href="#" onClick={e => {e.preventDefault(); loadPrev()}}>&larr;</a></div>
			<div className="sp_weekdisplay">Uge { week }, { year }</div>
			<div className="sp_next"><a href="#" onClick={e => {e.preventDefault(); loadNext()}}>&rarr;</a></div>
		</div>
		<div className="sp_days" style={{opacity: loaded ? undefined : 0.8}}>
			<ScheduleEdit data={data.current} />
		</div>
	</>;
}

(window as any).initScheduleEdit = (root: HTMLDivElement) => {
	ReactDOM.render(<ScheduleEditMain />, root);
};