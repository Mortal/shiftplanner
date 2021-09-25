import * as React from "react";

export const StringEdit: React.FC<{
	state: [string, (v: string) => void],
	save: () => void,
	placeholder?: string,
	multiline?: boolean,
}> = (props) => {
	const lineCount = props.state[0].split("\n").length;
	if (props.multiline) return <textarea
		value={props.state[0]}
		onChange={(e) => props.state[1](e.target.value)}
		placeholder={props.placeholder}
		style={{font: "inherit", flex: "1 0 auto"}}
		rows={lineCount}
	/>;
	const onKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.code !== "Enter") return;
		e.preventDefault();
		props.save();
	};
	return <input
		value={props.state[0]}
		onChange={(e) => props.state[1](e.target.value)}
		onKeyPress={onKeyPress}
		placeholder={props.placeholder}
		style={{flex: "1 0 auto"}}
	/>;
}

export const useEditables = (initials: string[]) => {
	const editors: [string, React.Dispatch<React.SetStateAction<string>>][] = [];
	let edited = false;
	for (const i of initials) {
		editors.push(React.useState(i));
		if (editors[editors.length - 1][0] !== i) edited = true;
	}
	const values = editors.map(([v]) => v);
	return [edited, values, editors] as [boolean, typeof values, typeof editors];
}