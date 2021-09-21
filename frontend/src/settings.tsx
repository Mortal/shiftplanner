import * as React from "react";
import { Nav } from "./base";

interface Workplace {
	id: number;
}

const Settings: React.FC<{workplace: Workplace}> = (props) => {
	return <div>
		{props.workplace.id}
	</div>;
};

export const SettingsMain: React.FC<{}> = (_props) => {
	const [loaded, setLoaded] = React.useState(false);
	const workplace = React.useRef<{[idString: string]: any}>({});
	React.useEffect(
		() => {
			(async () => {
				const res = await window.fetch("/api/v0/workplace/");
				const data = await res.json();
				for (const row of data.rows) workplace.current[row.id + ""] = row;
				setLoaded(true);
			})();
		},
		[]
	)
	return <>
		<Nav current="settings" />
		{loaded ? <Settings workplace={[...workplace.current.values()][0]} /> : <div>Indlæser...</div>}
	</>;
}