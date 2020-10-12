'use strict';

function getTimeLeft(time) {
    var current_time = new Date();
    var end = new Date(time * 1000);
    var time_left = (end - current_time) / 1000;
    if (time_left <= 0) {
        return 'Time left: deadline over';
    } else {
        var days = Math.floor(time_left / 86400);
        var hours = Math.
        floor(((time_left / 86400) - days) * 24);
        var mins = Math.floor(((((time_left / 86400) - days) * 24) - hours) * 60);
        var secs = Math.floor(((((((time_left / 86400) - days) * 24) - hours) * 60) - mins) * 60);
    }

    return 'Time left: ' + days + ' days ' + hours + " hours, " + mins + " mins, " + secs + " secs left !";
}

function setUpTimer(events) {
    window.setInterval(() => {
        events.forEach((event) => {
            var deadline = getTimeLeft(event.time);
            if(document.querySelector('[data-id="' + event.id + '"] .event_deadline'))
                document.querySelector('[data-id="' + event.id + '"] .event_deadline').innerHTML = deadline;
        })

    }, 1000)
}

function deleteEvent(eventId) {
    console.log(eventId);

    fetch(`/event/${eventId}`, {
            method: 'DELETE'
        }).then(response => response.json())
        .then((json) => {
            console.log('success!!')
            console.log(json);
            fetchEvents();
        })
        .catch(error => error);
}

function reqJSON(method, path, data) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(method, path, true);
        xhr.setRequestHeader('Content-type', 'application/json');
        xhr.responseType = 'json';

        function resp() {
            return {
                status: xhr.status,
                statusText: xhr.statusText,
                data: xhr.response,
            }
        }
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(resp());
            } else {
                console.error('xhr with error:', xhr);
                reject(resp());
            }
        }
        xhr.onerror = () => {
            console.error('xhr with error:', xhr);
            reject(resp());
        }
        xhr.send(JSON.stringify(data));
    })
}

function renderEvents(events) {
    let events_list_html = '';
    events.forEach((event) => {
        if (event.time)
            events_list_html += `<div data-id="${event.id}" class="event">
                                                <p class="event_name">Name: "${event.name}"</p>
                                                <p class="event_date">Date: ${new Date(event.time * 1000).toLocaleDateString("en-US")}</p>
                                                <p class="event_deadline">${getTimeLeft(event.time)}</p>
                                                <input type='button' data-id="${event.id}" onclick='deleteEvent(this.getAttribute("data-id"))' value='Delete event' style='cursor: pointer;'>
                                            </div><br>`;
    })
    document.getElementById('events_list').innerHTML = events_list_html;
    setUpTimer(events);
}

async function fetchEvents() {
    try{
        let { data } = await reqJSON('GET', '/events');
        let current_time = new Date();
        console.log(data);
        let final_events = []
        data.forEach((event) => {
            if(!event.recurring){
                final_events.push(event);
            }
        });
        let recurring_events = data.filter((event) => event.recurring);
        let recurring_events_grouped = {}
        recurring_events.forEach((recurring_event) => {
            if(!recurring_events_grouped[recurring_event['name']])
                recurring_events_grouped[recurring_event['name']] = [recurring_event];
            else
                recurring_events_grouped[recurring_event['name']].push(recurring_event);
        });
        console.log(recurring_events_grouped);
        for (const event_name in recurring_events_grouped) {
            let future_events = recurring_events_grouped[event_name].filter((event) => new Date(event.time * 1000) > current_time);
            if(future_events[0])
                final_events.push(future_events[0]);
            if(future_events[1])
                final_events.push(future_events[1]);
        }
        renderEvents(final_events)
    }
    catch(e){
        console.log(e);
        if(e.data.data)
            alert(e.data.data);
        if(e.status == 401){ // Delete session cookie and redirect to login
            document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            window.location.href = '/login';
        }
    }

}

async function logout(){
    // document.cookie = "session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    // window.location.href = '/login';
    await reqJSON('GET', '/logout');
}
function addEvent() {
    if (document.querySelector('input[name="event_name"]').value == '' 
        || document.querySelector('input[name="event_month"]').value == ''
        || document.querySelector('input[name="event_day"]').value == '' 
        || document.querySelector('input[name="event_time"]').value == '') {
        alert('Add all the inputs');
        return;
    }
    var data = new FormData();
//     var date = document.querySelector('input[name="event_date"]').value;
    var year = document.querySelector('input[name="event_year"]').value;
    var month = document.querySelector('input[name="event_month"]').value;
    var day = document.querySelector('input[name="event_day"]').value;
    var time = document.querySelector('input[name="event_time"]').value;
    var t = time.split(':');
//     var d = date.split('-');
    var epoch = (new Date(year, month - 1, day, t[0], t[1], t[2] || 0)).valueOf();
    console.log(new Date(year, month - 1, day, t[0], t[1], t[2] || 0));
    data.append('event_name', document.querySelector('input[name="event_name"]').value);
    data.append('event_date', epoch / 1000);
    data.append('event_year', document.querySelector('input[name="event_year"]').value);
    data.append('event_month', document.querySelector('input[name="event_month"]').value);
    data.append('event_day', document.querySelector('input[name="event_day"]').value);

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/events', true);
    xhr.onload = function() {
        if (this.status == 200) {
            alert('Event successfully added');
            console.log(this.responseText);
            fetchEvents();
        }
    };
    xhr.send(data);
}
window.addEventListener('load', function() {
    fetchEvents();
});