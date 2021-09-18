import * as React from "react";
import * as ReactDOM from "react-dom";

interface Worker {
	id: number;
	name: string;
	phone: string;
	login_secret: string;
}

interface Workers {
	loadCount: number;
	workers: {[id: string]: Worker};
}

const WorkerListContext = React.createContext<{[id: string]: Worker}>({});

// From https://docs.djangoproject.com/en/3.2/ref/csrf/
function getCookie(name: string) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const ShiftEdit: React.FC<{row: any, onRefresh: () => void}> = (props) => {
	const { row, onRefresh } = props;
	const [addShown, setAddShown] = React.useState(false);

	const addWorker = async (worker: Worker) => {
		const csrftoken = getCookie('csrftoken') || "";
		const body = new URLSearchParams(
			{
				"workers": JSON.stringify([...row.workers, worker]),
			}
		);
		const res = await window.fetch(
			`/api/v0/shift/${row.id}/`,
			{
				method: "POST",
				body,
				headers: {'X-CSRFToken': csrftoken},
			}
		);
		if (!res.ok) {
			console.log(`HTTP ${res.status} when adding worker`);
		}
		onRefresh();
	}
	return <div className="sp_shift">
		<h2>{ row.name }</h2>
		<ol>
			{row.workers.map(({name}: {name: string}, i: number) => <li key={i}>{name}</li>)}
			<li style={{listStyle: "none"}}>
				{addShown
				? <WorkerListContext.Consumer>
					{(workers) => 
					<select onChange={(e) => {addWorker(workers[e.target.value]); setAddShown(false);}}>
						<option></option>
						{Object.entries(workers).map(
							([id, worker]) =>
							<option value={id} key={id}>{worker.name}</option>
						)}
					</select>}
				</WorkerListContext.Consumer>
				: <a href="#" onClick={(e) => {e.preventDefault(); setAddShown(true)}}>Tilføj</a>}
			</li>
		</ol>
	</div>;
}

const DayEdit: React.FC<{date: string, rows: any[], onRefresh: () => void}> = (props) => {
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
		{rows.map((row) => <ShiftEdit key={row.order} row={row} onRefresh={props.onRefresh} />)}
	</div>;
}

const ScheduleEdit: React.FC<{data: any[], onRefresh: () => void}> = (props) => {
	const { data } = props;
	const dataByDate: {[date: string]: any[]} = {};
	for (const row of data) {
		(dataByDate[row.date] || (dataByDate[row.date] = [])).push(row);
	}
	return <>
		{Object.entries(dataByDate).map(
			([date, rows]) => (
				<DayEdit key={date} date={date} rows={rows} onRefresh={props.onRefresh} />
			)
		)}
	</>;
}

const ScheduleEditMain: React.FC = (_props: {}) => {
	const [error, setError] = React.useState("");

	const [refreshCount, setRefreshCount] = React.useState(0);
	const [weekYear, setWeekYear] = React.useState({week: 0, year: 0, refreshCount});
	const [weekYearLoading, setWeekYearLoading] = React.useState({week: 1, year: 2022, relative: 0});
	const loaded =
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
			setWeekYear({week: w, year: y, refreshCount});
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
	const onRefresh = React.useCallback(
		() => setRefreshCount((refreshCount) => refreshCount + 1),
		[]
	);

	return <WorkerListContext.Provider value={workers.current.workers}>
		{error !== "" && <div className="sp_error">{error}</div>}
		<div className="sp_weekheader">
			<div className="sp_prev"><a href="#" onClick={e => {e.preventDefault(); loadPrev()}}>&larr;</a></div>
			<div className="sp_weekdisplay">Uge { week }, { year }</div>
			<div className="sp_next"><a href="#" onClick={e => {e.preventDefault(); loadNext()}}>&rarr;</a></div>
		</div>
		<div className="sp_days" style={{opacity: loaded ? undefined : 0.8}}>
			<ScheduleEdit data={data.current} onRefresh={onRefresh} />
		</div>
	</WorkerListContext.Provider>;
}

(window as any).initScheduleEdit = (root: HTMLDivElement) => {
	ReactDOM.render(<ScheduleEditMain />, root);
};