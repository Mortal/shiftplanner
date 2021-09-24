import * as React from "react";

export interface Worker {
	id: number;
	name: string;
	phone: string;
	login_secret: string;
	active: boolean;
	note: string;
}

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

export interface WorkplaceSettings {
	weekday_defaults?: WeekdayDefaults;
	default_view_day?: string;
	message_of_the_day?: string;
	print_header_text?: string;
	max_print_per_shift?: number;
	login_email_template?: string;
	login_email_subject?: string;
	login_sms_template?: string;
	country_code?: string;
}

export interface Workplace {
	id: number;
	settings: WorkplaceSettings;
}

export const WorkerListContext = React.createContext<{[id: string]: Worker}>({});
export const WorkplaceSettingsContext = React.createContext<WorkplaceSettings>({});

// From https://docs.djangoproject.com/en/3.2/ref/csrf/
export function getCookie(name: string) {
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

export const fetchPost = (url: string, body: any) => {
	const csrftoken = getCookie('csrftoken') || "";
	return window.fetch(
		url,
		{
			method: "POST",
			body: JSON.stringify(body),
			headers: {'X-CSRFToken': csrftoken},
		}
	);
};

export const Nav: React.FC<{current: string}> = (props) => {
	return <ul className="sp_nav">
		<li className={props.current === "schedule" ? "sp_current" : ""}>
			<a href="/admin/">Vagtplan</a>
		</li>
		<li className={props.current === "workers" ? "sp_current" : ""}>
			<a href="/admin/workers/">Vagttagere</a>
		</li>
		<li className={props.current === "settings" ? "sp_current" : ""}>
			<a href="/admin/settings/">Indstillinger</a>
		</li>
		<li>
			<a href="/adminlogout/">Log ud</a>
		</li>
	</ul>
}