# -*- coding: utf-8 -*-

# Copyright (C) 2014 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Narration of routing maneuvers."""

import bisect
import copy
import poor
import statistics

from poor.i18n import _
from poor.voicecommand import VoiceCommand

__all__ = ("Narrative",)


class VerbalPrompt:

    """Verbal prompt before a routing maneuver"""

    def __init__(self, distance, prompt):
        self.distance = distance
        self.prompt = prompt


class Maneuver:

    """A routing maneuver."""

    def __init__(self, **kwargs):
        """Initialize a :class:`Maneuver` instance."""
        self.duration = 0
        self.icon = "flag"
        self.length = 0
        self.narrative = ""
        self.verbal_alert = None
        self.verbal_pre = None
        self.verbal_post = None
        self.verbal_prompts_before = [] # verbal alerts and _pre
                                        # prompt arranged into a
                                        # list. The prompts are sorted
                                        # by the distance from the
                                        # maneuver
        self.verbal_alert_full = None
        self.node = None
        self.x = None
        self.y = None
        for name in set(kwargs) & set(dir(self)):
            setattr(self, name, kwargs[name])
        if self.verbal_alert is None: self.verbal_alert = self.narrative
        if self.verbal_pre is None: self.verbal_pre = self.narrative

    def is_same(self, maneuver):
        """Check if the maneuver matches self"""
        return ( maneuver.node == self.node )

class Narrative:

    """Narration of routing maneuvers."""

    def __init__(self):
        """Initialize a :class:`Narrative` instance."""
        self.dist = []
        self._last_node = 0
        self.maneuver = []
        self.mode = "car"
        self.time = []
        self.x = []
        self.y = []
        self.current_maneuver = None
        self.distance_route_too_far = 200.0 # [meter] used to check whether route is too far to display instructions
        self.distance_route_too_far_for_direction = 50.0 # [meter] don't auto-rotate when exceeding this distance
        self.distance_route_init_reroute = 200.0 # [meter] when distance from route is exceeded, triggers rerouting calculations
        self.voice_engine = VoiceCommand()
        # voice commands: alert and pre parameters
        self.voice_alert_distance = 200
        self.voice_alert_time = 30
        self.voice_pre_distance = 50
        self.voice_pre_time = 5

        self.navigation_active = False # True while navigating

    def _calculate_direction_ahead(self, node):
        """Return direction of the segment from `node` ahead."""
        return poor.util.calculate_bearing(
            self.x[node], self.y[node], self.x[node+1], self.y[node+1])

    def _calculate_length_ahead(self, node):
        """Return length of the segment from `node` ahead."""
        return poor.util.calculate_distance(
            self.x[node], self.y[node], self.x[node+1], self.y[node+1])

    def _get_closest_maneuver_node(self, x, y, node):
        """Return index of the maneuver node closest to coordinates."""
        if self.maneuver[node].node == node: return node
        # Only consider the immediate preceding and following
        # maneuver nodes from the given closest route node.
        nodes = sorted(set(x.node for x in self.maneuver if x))
        a = bisect.bisect_left(nodes, node)
        b = bisect.bisect_right(nodes, node)
        nodes = nodes[max(0, a-1):min(len(nodes), b+1)]
        return poor.util.find_closest(self.x, self.y, x, y, nodes)

    def _get_closest_node(self, x, y):
        """Return index of the route node closest to coordinates."""
        return poor.util.find_closest(self.x, self.y, x, y)

    def _get_closest_segment_node(self, x, y):
        """Return index of a node of the segment closest to coordinates."""
        min_node = 0
        min_dist = 360**2
        eps1 = 0.00005**2
        eps2 = 0.0002**2
        eps3 = 0.005**2
        ahead = range(self._last_node, len(self.x) - 1)
        behind = reversed(range(0, self._last_node))
        for iterator in (ahead, behind):
            for i in iterator:
                # This should be faster than haversine
                # and probably close enough.
                dist = poor.polysimp.get_sq_seg_dist(
                    x, y, self.x[i], self.y[i], self.x[i+1], self.y[i+1])
                if dist < min_dist:
                    min_node = i
                    min_dist = dist
                # Try to terminate as soon as possible.
                # These conditions will fail if off route.
                if min_dist < eps1: break
                if min_dist < eps2 and dist > eps3: break
        self._last_node = min_node
        a, b = min_node, min_node + 1
        dist_a = (x - self.x[a])**2 + (y - self.y[a])**2
        dist_b = (x - self.x[b])**2 + (y - self.y[b])**2
        return (a if dist_a < dist_b else b)

    def _get_direction(self, x, y, node):
        """Return the direction of the route at `node`."""
        if node > 0:
            # The closest segment is right before or after the closest node.
            dist = (x - self.x[node])**2 + (y - self.y[node])**2
            dist_prev = (x - self.x[node-1])**2 + (y - self.y[node-1])**2
            if dist_prev < dist: node -= 1
        node = max(0, min(len(self.x) - 2, node))
        # If the closest route segment is very short, it could be a lane change
        # or something else unordinary, which we are unlikely to want to rotate
        # over. Find segments to cover a minimum distance and take the median
        # of their individual directions to dampen irrelevant variation.
        length = self._calculate_length_ahead(node)
        directions = [self._calculate_direction_ahead(node)]
        r = 1
        while length < 50 and node - r >= 0 and node + r < len(self.x) - 1:
            directions.append(self._calculate_direction_ahead(node - r))
            directions.append(self._calculate_direction_ahead(node + r))
            length += self._calculate_length_ahead(node - r)
            length += self._calculate_length_ahead(node + r)
            r += 1
        return statistics.median(directions)

    def _get_distance_from_route(self, x, y, node):
        """Return distance in meters from the route polyline."""
        return min(self._get_distances_from_route(x, y, node))

    def _get_distances_from_route(self, x, y, node):
        """Return distances in meters from route segments."""
        if len(self.x) == 1:
            return poor.util.calculate_distance(
                x, y, self.x[node], self.y[node])
        dist = []
        if node > 0:
            x1, x2 = self.x[node-1:node+1]
            y1, y2 = self.y[node-1:node+1]
            dist.append(poor.util.calculate_segment_distance(
                x, y, x1, y1, x2, y2))
        if node < len(self.x) - 1:
            x1, x2 = self.x[node:node+2]
            y1, y2 = self.y[node:node+2]
            dist.append(poor.util.calculate_segment_distance(
                x, y, x1, y1, x2, y2))
        return dist

    def get_display(self, x, y, accuracy=None):
        """Return a dictionary of status details to display."""
        if not self.ready: return None
        if self.mode == "transit":
            return self._get_display_transit(x, y)
        node = self._get_closest_segment_node(x, y)
        seg_dists = self._get_distances_from_route(x, y, node)
        seg_dist = min(seg_dists)
        dest_dist, dest_time = self._get_display_destination(
            x, y, node, seg_dist)
        dest_dist = poor.util.format_distance(dest_dist)
        dest_time = poor.util.format_time(dest_time)
        man = self._get_display_maneuver(x, y, node, seg_dists)
        man_node, man_dist, man_time, icon, narrative, maneuver = man
        man_dist_value, man_time_value = man_dist, man_time
        man_dist = poor.util.format_distance(man_dist)
        man_time = poor.util.format_time(man_time)
        if seg_dist > self.distance_route_too_far:
            # Don't show the narrative or details calculated
            # from nodes along the route if far off route.
            dest_time = man_time = icon = narrative = None

        # Don't provide route direction to auto-rotate by if off route.
        direction = self._get_direction(x, y, node) if seg_dist < self.distance_route_too_far_for_direction else None
        # Trigger rerouting if far off route.
        reroute = seg_dist > self.distance_route_init_reroute + (accuracy or 40000000)

        # voice commands support
        voice_to_play = None
        if ( self.navigation_active and
             self.voice_engine.active() and
             seg_dist < self.distance_route_too_far_for_direction ):
            # no voice commands when too far from the route

            if self.current_maneuver is None:
                # just starting, not much to do this time
                self._set_current_maneuver(maneuver)

            elif self.current_maneuver.is_same(maneuver):

                for i in range(len(self.current_maneuver.verbal_prompts_before)):
                    p = self.current_maneuver.verbal_prompts_before[i]
                    if man_dist_value < p.distance + 10: # use 10 meters as a tolerance
                        voice_to_play = self.voice_engine.get(p.prompt)
                        if voice_to_play is not None:
                            # drop the played prompt and all that were
                            # supposed to be played before
                            self.current_maneuver.verbal_prompts_before = self.current_maneuver.verbal_prompts_before[:i]
                        break

                else: # not much to do, use for maintenance
                    self.voice_engine.set_time(self.time[node])

            else: # maneuver changed

                # post voice should be played only if we are moving
                # along the road. in this case, new maneuver should be
                # the next one for the current_maneuver.
                if ( self.current_maneuver.verbal_post is not None and
                     self.current_maneuver.node + 1 < len(self.maneuver) and
                     self.maneuver[self.current_maneuver.node+1].is_same(maneuver) ):
                    voice_to_play = self.voice_engine.get(self.current_maneuver.verbal_post)
                    if voice_to_play is not None:
                        self.current_maneuver.verbal_post = None
                self._set_current_maneuver(maneuver)

        return dict(total_dist=poor.util.format_distance(max(self.dist)),
                    total_time=poor.util.format_time(max(self.time)),
                    dest_dist=dest_dist,
                    dest_time=dest_time,
                    man_dist=man_dist,
                    man_time=man_time,
                    icon=icon,
                    narrative=narrative,
                    direction=direction,
                    reroute=reroute,
                    voice_to_play=voice_to_play)

    def _get_display_destination(self, x, y, node, seg_dist):
        """Return destination details to display."""
        dest_dist = seg_dist + self.dist[node]
        dest_time = self.time[node]
        if node == len(self.x) - 1 or dest_dist < 500:
            # Use exact straight-line value at the very end.
            dest_dist = poor.util.calculate_distance(
                x, y, self.maneuver[node].x, self.maneuver[node].y)
        return dest_dist, dest_time

    def _get_display_maneuver(self, x, y, node, seg_dists):
        """Return maneuver details to display."""
        # For car, show narrative of the next maneuver point following
        # the closest route segment, but avoid considering the maneuver point
        # passed too soon in case the positioning jumps around a bit.
        if len(seg_dists) == 2:
            # If the segment following the closest node is closer than
            # the one preceding, use the maneuver data of the next node.
            s1, s2 = seg_dists
            if s2 < s1/2 and s1 > 10:
                node = node + 1
        seg_dist = min(seg_dists)
        maneuver = self.maneuver[node]
        man_node = maneuver.node
        man_dist = seg_dist + self.dist[node] - self.dist[man_node]
        man_time = self.time[node] - self.time[man_node]
        if node == man_node or man_dist < 500:
            # Use exact straight-line value at the very end.
            man_dist = poor.util.calculate_distance(
                x, y, maneuver.x, maneuver.y)
        return man_node, man_dist, man_time, maneuver.icon, maneuver.narrative, maneuver

    def _get_display_transit(self, x, y):
        """Return a dictionary of status details to display."""
        # For transit, show narrative of the closest node, since transit
        # maneuver points are not always points, but often stations or
        # platforms that cover a large area.
        node = self._get_closest_segment_node(x, y)
        seg_dist = self._get_distance_from_route(x, y, node)
        dest_dist, dest_time = self._get_display_destination(
            x, y, node, seg_dist)
        dest_dist = poor.util.format_distance(dest_dist)
        dest_time = poor.util.format_time(dest_time)
        man_node = self._get_closest_maneuver_node(x, y, node)
        if man_node > node + 1:
            # If the maneuver point is far and still ahead, we can calculate
            # distances and times from along the route, just as for cars.
            man_dist = seg_dist + self.dist[node] - self.dist[man_node]
            man_time = self.time[node] - self.time[man_node]
        else:
            # If the maneuver point is the very next one,
            # or already passed, use straight-line distance.
            man_dist = poor.util.calculate_distance(
                x, y, self.maneuver[man_node].x, self.maneuver[man_node].y)
            man_time = 0
        if node > man_node and man_dist > 500:
            # If closest maneuver point surely passed,
            # show narrative of the next maneuver.
            man_dist = poor.util.calculate_distance(
                x, y, self.maneuver[node].x, self.maneuver[node].y)
            icon = self.maneuver[node].icon
            narrative = self.maneuver[node].narrative
        else:
            # If near a maneuver point,
            # show the corresponding narrative.
            icon = self.maneuver[man_node].icon
            narrative = self.maneuver[man_node].narrative
        man_dist = poor.util.format_distance(man_dist)
        man_time = poor.util.format_time(man_time)
        # Don't provide route direction to auto-rotate by if off route.
        direction = self._get_direction(x, y, node) if seg_dist < 50 else None
        return dict(total_dist=poor.util.format_distance(max(self.dist)),
                    total_time=poor.util.format_time(max(self.time)),
                    dest_dist=dest_dist,
                    dest_time=dest_time,
                    man_dist=man_dist,
                    man_time=man_time,
                    icon=icon,
                    narrative=narrative,
                    direction=direction,
                    reroute=False,
                    voice_to_play=None)

    def _set_current_maneuver(self, maneuver):
        """Set the current maneuver and request the corresponding voice commands"""
        # set current maneuver
        self.current_maneuver = copy.deepcopy(maneuver)

        if not self.voice_engine.active():
            return

        # request to make voice commands
        time = self.time[maneuver.node]
        for p in self.current_maneuver.verbal_prompts_before:
            self.voice_engine.make(p.prompt, time)

        if self.current_maneuver.verbal_post:
            self.voice_engine.make(self.current_maneuver.verbal_post, time)

    def get_maneuvers(self, x, y):
        """Return a list of dictionaries of maneuver details."""
        node = self._get_closest_segment_node(x, y)
        man_node = self._get_closest_maneuver_node(x, y, node)
        maneuvers = filter(None, set(self.maneuver))
        maneuvers = sorted(maneuvers, key=lambda x: x.node)
        return [dict(active=(maneuver.node == man_node),
                     icon=maneuver.icon,
                     length=poor.util.format_distance(maneuver.length),
                     narrative=maneuver.narrative,
                     x=maneuver.x,
                     y=maneuver.y,
                     ) for maneuver in maneuvers]

    @property
    def ready(self):
        """Return ``True`` if narrative is in steady state and ready for use."""
        return (self.x and
                len(self.x) ==
                len(self.y) ==
                len(self.dist) ==
                len(self.time) ==
                len(self.maneuver))

    def set_maneuvers(self, maneuvers):
        """
        Set maneuver points and corresponding narrative.

        Keys "x", "y" and "duration" are required for each item in `maneuvers`
        and keys "icon", "narrative" and "passive" are optional. Duration
        (seconds) refers to the leg following the maneuver, other data is
        associated with the maneuver point itself.
        """
        self.current_maneuver = None
        self.voice_engine.clean()
        prev_maneuver = None
        for i in reversed(range(len(maneuvers))):
            if maneuvers[i].get("passive", False): continue
            maneuver = Maneuver(**maneuvers[i])
            maneuver.node = self._get_closest_node(maneuver.x, maneuver.y);
            self.maneuver[maneuver.node] = maneuver
            # Assign maneuver to preceding nodes as well.
            for j in reversed(range(maneuver.node)):
                self.maneuver[j] = maneuver
            # Calculate time remaining to destination for each node
            # based on durations of individual legs following given maneuvers.
            if prev_maneuver is not None:
                prev_dist = self.dist[prev_maneuver.node]
                maneuver.length = self.dist[maneuver.node] - prev_dist
                speed = maneuver.length / max(1, maneuver.duration) # m/s

                ##################################################
                # voice prompts support
                maneuver.verbal_prompts_before = []

                if maneuver.verbal_pre is not None:
                    distance_pre = max( self.voice_pre_distance, self.voice_pre_time*speed )
                    maneuver.verbal_prompts_before.append( VerbalPrompt(distance = distance_pre,
                                                                        prompt = maneuver.verbal_pre) )
                if maneuver.verbal_alert is not None:
                    distance_alert = min(maneuver.length,
                                         max(self.voice_alert_distance,
                                             self.voice_alert_time*speed) )
                    prompt = _("In {distance}, {command}").format(
                        distance = poor.util.format_distance(distance_alert, voice=True),
                        command = maneuver.verbal_alert)

                    maneuver.verbal_prompts_before.append( VerbalPrompt(distance = distance_alert,
                                                                        prompt = prompt) )
                # voice prompts: done

                for j in reversed(range(maneuver.node, prev_maneuver.node)):
                    dist = self.dist[j] - self.dist[j+1]
                    self.time[j] = self.time[j+1] + dist/speed
            prev_maneuver = maneuver

    def set_mode(self, mode):
        """
        Set transport mode for route.

        `mode` should be "car" or "transit". This affects how maneuver
        notifications are handled. Currently only transit (public
        transportation) is handled differently and thus walking, bicycle, etc.
        can all be marked as "car".
        """
        self.mode = mode

    def set_voice(self, language, sex = "male"):
        """Set voice commands mode"""
        self.voice_engine.set_voice(language, sex)

    def set_route(self, x, y):
        """Set route from coordinates."""
        self.x = x
        self.y = y
        self.dist = [0] * len(x)
        self.time = [0] * len(x)
        self.maneuver = [None] * len(x)
        self._last_node = 0
        for i in list(reversed(range(len(x) - 1))):
            dist = poor.util.calculate_distance(x[i], y[i], x[i+1], y[i+1])
            if dist < 1:
                # Consecutive duplicate points will cause problems for
                # calculations that determine when to show narrative related
                # to a maneuver point. We need to drop these.
                del self.x[i]
                del self.y[i]
                del self.dist[i]
                del self.time[i]
                del self.maneuver[i]
                continue
            self.dist[i] = self.dist[i+1] + dist
            # Calculate remaining time using 120 km/h, which will maximize
            # the advance at which maneuver notifications are shown.
            # See 'set_maneuvers' for the actual leg-specific times
            # that should in most cases overwrite these.
            self.time[i] = self.time[i+1] + (dist/1000/120) * 3600

    def unset(self):
        """Unset route and maneuvers."""
        self.dist = []
        self._last_node = 0
        self.maneuver = []
        self.mode = "car"
        self.time = []
        self.x = []
        self.y = []
        self.current_maneuver = None

    def begin(self):
        """Begin navigation"""
        self.current_maneuver = None
        self.navigation_active = True
        #print("Navigation started")

    def end(self):
        """End navigation"""
        self.current_maneuver = None
        self.navigation_active = False
        #print("Navigation stopped")

    def quit(self):
        """Cleanup before quiting application"""
        del self.voice_engine
        self.voice_engine = None
