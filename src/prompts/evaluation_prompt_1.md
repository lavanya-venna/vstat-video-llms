Watch the whole video carefully.

Question: {question}

Answer by writing a record of what happens in the video, in exactly this format:

PLAN
STATE: <name> : <what you must keep track of> (<element>, <structure>)
ENT: <id> = <what it looks like> ; at start: <where it is, or what state it is in>
EVENTS: <the kinds of event that can change the state>
SCOPE: <the part of the video the question is about>
INIT: <value of each STATE variable at the start of the scope>
RECORD
EVT: <event>(<ids and details>) from <start>s to <end>s
UPD: <current value of each STATE variable> | <a few words on why>
(repeat EVT and UPD for every event)
READ: <how the answer follows from the final state>
ANSWER: {answer_rule}

Write only these lines, as plain text: no markdown, no bullet points, no other commentary.

How to fill in each part

STATE
•⁠  ⁠Take it from the question. Decide what you must keep track of to answer, which can differ from the answer itself: to answer "how many different people came in?", keep a set of people.
•⁠  ⁠element is count (how many things or times), location (where something is) or attribute (what something is like, or which one it is).
•⁠  ⁠structure is atomic (one value), sequence (an ordered list), set (an unordered group) or dictionary (one value per key, such as per team or per object).
•⁠  ⁠If one variable is not enough (a percentage needs two counts, for example), write up to three STATE lines, the main one first.

ENT
•⁠  ⁠Take it from the start of the video. Write one line for each object or person the state depends on.
•⁠  ⁠If the question names or numbers the objects, use its names as ids.
•⁠  ⁠Otherwise name objects by how they look (colour, number, markings), never by where they are, because positions change.
•⁠  ⁠If several look identical, number them by where they start (item_1 is the one that starts on the left). An id stays with its object when it moves or is hidden.

SCOPE
•⁠  ⁠Write "whole video", or the part the question asks about with its times, for example "after the door opens, 12s to 40s".

EVT and UPD
•⁠  ⁠Write one EVT line per event, in time order. Do not merge events and do not skip any.
•⁠  ⁠Follow every EVT with one UPD, even when nothing changed. Many events look important but leave the state as it was: write the value again and say why.
•⁠  ⁠UPD gives the full current value of every STATE variable, not just the part that changed.
•⁠  ⁠Add (unsure) at the end of an EVT line when you could not see the event clearly, for example because it was hidden or too fast. Still write your best guess.
•⁠  ⁠If nothing in the scope changes the state, write no EVT or UPD lines.

READ and ANSWER
•⁠  ⁠READ shows how the answer follows from the final state, including any counting or arithmetic.
•⁠  ⁠ANSWER must be exactly what READ gives.
•⁠  ⁠For a multiple-choice question, ANSWER is only the letter, even if the question asks for the answer in another form. For a number question, it is only the integer, rounded as the question asks.

Rules
•⁠  ⁠Base every line on what you see in this video, not on what usually happens.
•⁠  ⁠Apply every rule in the question (what counts, what does not, whose left or right) when deciding which events to record and how they change the state.
•⁠  ⁠Positions are as the viewer sees them unless the question says otherwise. If the camera moves in a way that changes how positions look, record that as an EVT.
•⁠  ⁠Times are seconds from the start of the video. Rough times are fine, but they must go forward.
•⁠  ⁠Every change to the state must come from an EVT line.

Writing values
•⁠  ⁠atomic: count = 3
•⁠  ⁠sequence: stops = [bakery, bank, park]
•⁠  ⁠set: came_in = {man_cap, woman_red_coat}
•⁠  ⁠dictionary: spot = {van_white: 1, car_grey_1: out}   (keys still at zero or empty can be left out)
•⁠  ⁠several variables: sold = {apples: 2} ; stock = {apples: 5}

Example (format only: your STATE, ENT and EVENTS must come from your own question and video)

Question: Which spot is the white van in at the end of the video?
(A) Spot 1
(B) Spot 2
(C) Spot 3
(D) Not in the lot

PLAN
STATE: spot : which parking spot each vehicle is in (location, dictionary)
ENT: van_white = white van ; at start: spot 1
ENT: car_grey_1 = grey sedan ; at start: spot 2
ENT: car_grey_2 = grey sedan, identical to car_grey_1 ; at start: spot 3
EVENTS: move(vehicle, spot), leave(vehicle), reverse(vehicle)
SCOPE: whole video
INIT: spot = {van_white: 1, car_grey_1: 2, car_grey_2: 3}
RECORD
EVT: leave(car_grey_1) from 3.0s to 5.5s
UPD: spot = {van_white: 1, car_grey_1: out, car_grey_2: 3} | car_grey_1 drove out of spot 2
EVT: reverse(car_grey_2) from 6.0s to 8.0s
UPD: spot = {van_white: 1, car_grey_1: out, car_grey_2: 3} | it pulled back into spot 3, so nothing changed
EVT: move(van_white, 2) from 10.0s to 13.5s (unsure)
UPD: spot = {van_white: 2, car_grey_1: out, car_grey_2: 3} | the van took the free spot 2; a truck blocked part of the view
READ: spot[van_white] = 2, which is Spot 2
ANSWER: B
