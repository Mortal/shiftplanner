import * as React from "react";
import { fetchPost, Nav, Workplace } from "./base";
import { StringEdit, useEditables } from "./utils";

const EditRow: React.FC<{ title: React.ReactNode, help: React.ReactNode }> = (props) => (
	<div className="sp_EditRow">
		<div>{props.title}</div>
		<div>
			<div>{props.children}</div>
			<div>{props.help}</div>
		</div>
	</div>
)

const Settings: React.FC<{workplace: Workplace, save: (w: Workplace) => Promise<{ok?: any, error?: any, debug?: any}>}> = (props) => {
	const settings = props.workplace.settings;
	const [serverError, setServerError] = React.useState("");
	const [edited, values, [
		defaultViewDay,
		messageOfTheDay,
		printHeaderText,
		maxPrintPerShiftString,
		loginEmailTemplate,
		loginEmailSubject,
		loginSmsTemplate,
		countryCode
	]] = useEditables(
		[
			settings.default_view_day || "",
			settings.message_of_the_day || "",
			settings.print_header_text || "",
			(settings.max_print_per_shift || "") + "",
			settings.login_email_template || "",
			settings.login_email_subject || "",
			settings.login_sms_template || "",
			settings.country_code || "",
		]
	);
	const maxPrintPerShift = parseInt(maxPrintPerShiftString[0]);
	const valid = !isNaN(maxPrintPerShift) && (maxPrintPerShift + "" === maxPrintPerShiftString[0]);
	React.useEffect(
		() => {
			if (!edited && valid) setServerError("");
		},
		[serverError, edited, valid]
	);

	const save = React.useCallback(
		async () => {
			if (!edited) {
				setServerError("");
				return;
			}
			if (!valid) {
				setServerError("'Maks antal vagttagere' skal være et tal");
				return;
			}
			const [
				defaultViewDay,
				messageOfTheDay,
				printHeaderText,
				_maxPrintPerShiftString,
				loginEmailTemplate,
				loginEmailSubject,
				loginSmsTemplate,
				countryCode
			] = values;
			const res = await props.save({
				...props.workplace,
				settings: {
					default_view_day: defaultViewDay,
					message_of_the_day: messageOfTheDay,
					print_header_text: printHeaderText,
					max_print_per_shift: maxPrintPerShift,
					login_email_template: loginEmailTemplate,
					login_email_subject: loginEmailSubject,
					login_sms_template: loginSmsTemplate,
					country_code: countryCode,
				},
			});
			if (res.ok) setServerError("");
			else if (typeof res.error === "string") setServerError(res.error);
			else setServerError(`Fejl fra serveren: ${JSON.stringify(res)}`);
		},
		[edited, valid, maxPrintPerShift, ...values],
	);
	return <div>
		<EditRow
			title=""
			help="">
			<button className="sp_settings_save" disabled={!edited} onClick={() => save()}>Gem</button>
			{serverError && <div style={{marginLeft: "10px", color: "red", fontWeight: "bold"}}>{serverError}</div>}
		</EditRow>
		<EditRow
			title="Standard ugevisning"
			help={`Antal dage ud i fremtiden for den uge der skal vises.
			'9d'=Vis næste uge, undtaget lørdag og søndag hvor der skal vises ugen efter.`}>
			<StringEdit state={defaultViewDay} save={save} />
		</EditRow>
		<EditRow
			title="Besked til alle"
			help="Vis en besked til alle øverst på hver side"
		>
			<StringEdit state={messageOfTheDay} save={save} />
		</EditRow>
		<h2>Printvisning</h2>
		<EditRow
			title="Maks antal vagttagere"
			help="Maks antal vagttagere der skal vises pr. vagt i printvisning."
		>
			<StringEdit state={maxPrintPerShiftString} save={save} />
		</EditRow>
		<EditRow
			title="Tekst"
			help="Tekst der skal stå øverst på den printede vagtplan."
		>
			<StringEdit multiline state={printHeaderText} save={save} />
		</EditRow>
		<h2>Vagttagere</h2>
		<EditRow
			title="Email-emne"
			help="Standard emnefelt når man ønsker at sende login-link til vagttagere."
		>
			<StringEdit state={loginEmailSubject} save={save} />
		</EditRow>
		<EditRow
			title="Email-tekst"
			help="Standard-tekst når man ønsker at sende login-link til vagttagere."
		>
			<StringEdit multiline state={loginEmailTemplate} save={save} />
		</EditRow>
		<EditRow
			title="SMS-tekst"
			help="Standard-tekst når man ønsker at sende login-link på SMS til vagttagere."
		>
			<StringEdit multiline state={loginSmsTemplate} save={save} />
		</EditRow>
		<EditRow
			title="Landekode"
			help="Standard-landekode (f.eks. +45) når der skal sendes SMS til vagttagere."
		>
			<StringEdit state={countryCode} save={save} />
		</EditRow>
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
	const save = React.useCallback<(w: Workplace) => Promise<{ok?: any, error?: any, debug?: any}>>(
		async (w: Workplace) => {
			const res = await fetchPost("/api/v0/workplace/", w);
			if (res.status === 400) {
				return await res.json();
			}
			if (!res.ok) {
				return {"error": `HTTP ${res.status}`};
			}
			workplace.current[w.id] = {
				...workplace.current[w.id],
				settings: {
					...workplace.current[w.id].settings,
					...w.settings,
				}
			}
			setLoaded((i) => i + 1);
			return await res.json();
		},
		[],
	)
	return <>
		<Nav current="settings" />
		{loaded ? <Settings save={save} workplace={[...Object.values(workplace.current)][0]} /> : <div>Indlæser...</div>}
	</>;
}