import * as React from "react";
import { fetchPost, Nav } from "./base";
import { StringEdit, useEditables } from "./utils";

interface DaySettings {
	registration_starts: string;
    registration_deadline: string;
    shifts: string[];
}

interface WeekdayDefaults {
	monday?: DaySettings;
    tuesday?: DaySettings;
    wednesday?: DaySettings;
    thursday?: DaySettings;
    friday?: DaySettings;
    saturday?: DaySettings;
    sunday?: DaySettings;
}

interface WorkplaceSettings {
	weekday_defaults?: WeekdayDefaults;
	default_view_day?: string;
	message_of_the_day?: string;
}

interface Workplace {
	id: number;
	settings: WorkplaceSettings;
}

const Settings: React.FC<{workplace: Workplace, save: (w: Workplace) => Promise<void>}> = (props) => {
	const settings = props.workplace.settings;
	const [edited, values, [defaultViewDay, messageOfTheDay]] = useEditables(
		[settings.default_view_day || "", settings.message_of_the_day || ""]
	)

	const save = React.useCallback(
		() => {
			if (!edited) return;
			const [defaultViewDay, messageOfTheDay] = values;
			props.save({
				...props.workplace,
				settings: {
					default_view_day: defaultViewDay,
					message_of_the_day: messageOfTheDay,
				},
			})
		},
		[edited, ...values],
	);
	return <div>
		<div><StringEdit state={defaultViewDay} save={save} /></div>
		<div><StringEdit state={messageOfTheDay} save={save} /></div>
		<div><button disabled={!edited} onClick={() => save()}>Gem</button></div>
	</div>;
};

export const SettingsMain: React.FC<{}> = (_props) => {
	const [loaded, setLoaded] = React.useState(0);
	const workplace = React.useRef<{[idString: string]: any}>({});
	React.useEffect(
		() => {
			(async () => {
				const res = await window.fetch("/api/v0/workplace/");
				const data = await res.json();
				for (const row of data.rows) workplace.current[row.id + ""] = row;
				setLoaded((i) => i + 1);
			})();
		},
		[]
	)
	const save = React.useCallback(
		async (w: Workplace) => {
			const res = await fetchPost("/api/v0/workplace/", w);
			if (!res.ok) {
				console.error("Posting workplace settings failed", res.status);
				return;
			}
			await res.json();
			workplace.current[w.id] = {
				...workplace.current[w.id],
				settings: {
					...workplace.current[w.id].settings,
					...w.settings,
				}
			}
			setLoaded((i) => i + 1);
		},
		[],
	)
	return <>
		<Nav current="settings" />
		{loaded ? <Settings save={save} workplace={[...Object.values(workplace.current)][0]} /> : <div>Indlæser...</div>}
	</>;
}