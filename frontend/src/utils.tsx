import * as React from "react";

export const StringEdit: React.FC<{
	state: [string, (v: string) => void],
	save: () => void,
	placeholder?: string,
}> = (props) => {
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