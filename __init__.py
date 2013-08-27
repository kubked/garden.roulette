'''
Roulette
========



Dependencies
------------

1. the garden package ``kivy.garden.tickline``. Use ``garden install tickline``
    to install it like any other garden package.
    
3. for getting the local timezone, Windows or Unix-based systems need to get
   the ``tzlocal`` python module. ``easy_install`` or ``pip install`` should
   suffice here. 
   
'''
from kivy.garden.roulettescroll import RouletteScrollEffect
from kivy.garden.tickline import Tick, Tickline, TickLabeller
from kivy.garden.timeline import Timeline, TimeTick, TimeLabeller, \
    round_time
from kivy.animation import Animation
from kivy.base import runTouchApp
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.text import Label as CoreLabel
from kivy.graphics.vertex_instructions import Rectangle
from kivy.lang import Builder
from kivy.metrics import sp, dp
from kivy.properties import ListProperty, ObjectProperty, AliasProperty, \
    NumericProperty, BooleanProperty, StringProperty, OptionProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from datetime import datetime
from numbers import Number
from pytz import UTC
try:
    from tzlocal import get_localzone
except ImportError:
    from jnius import autoclass
    from pytz import timezone
    TimeZone = autoclass('java.util.TimeZone')
    
    def get_localzone():
        return timezone(TimeZone.getDefault().getID())
    
def local_now():
    return get_localzone().localize(datetime.now())    



class SlotLabeller(TickLabeller):
    def __init__(self, tickline):
        self.instructions = {}
        self.re_init()
        self.tickline = tickline
        
    def re_init(self):
        self.to_pop = set(self.instructions)
        self.to_push = [] 
        
    def register(self, tick, tick_index, tick_info):
        tickline = self.tickline
        if tick_index not in self.instructions:
            self.to_push.append(tick_index)
            texture = tick.get_label_texture(tick_index)
        else:
            self.to_pop.remove(tick_index)
            texture = self.instructions[tick_index].texture
        if texture:
            if tickline.is_vertical():
                tick_pos = tick_info[1] + tick_info[3] / 2
                pos = (tickline.center_x - texture.width / 2, 
                       tick_pos - texture.height / 2)
            else:
                tick_pos = tick_info[0] + tick_info[2] / 2
                pos = (tick_pos - texture.width / 2, 
                       tickline.center_y - texture.height / 2)
            # only need to update the position if label is saved
            self.instructions.setdefault(tick_index, 
                Rectangle(texture=texture, size=texture.size,
                          group=self.group_id)).pos = pos
    def make_labels(self):  
        canvas = self.tickline.canvas
        for index in self.to_push:
            rect = self.instructions[index]
            canvas.add(rect)
        for index in self.to_pop:
            rect = self.instructions.pop(index)
            canvas.remove(rect)
                               
#===============================================================================
# Slots
#===============================================================================
class Slot(Tick):
    tick_size = ListProperty([0, 0])
    font_size = NumericProperty('20sp')
    int_valued = BooleanProperty(True)
    format_str = StringProperty('{}')
    def value_str(self, value):
        return self.format_str.format(value)
    def slot_value(self, index, *args, **kw):
        '''returns the selection value that corresponds to ``index``.
        Should be overriden if necessary.'''
        if self.int_valued:
            return int(round(index))
        return index
    def index_of(self, val, *args, **kw):
        '''returns the index that corresponds to a selection value ``val``.
        Should be override if necessary.'''
        return val
    def get_label_texture(self, index, **kw):
        label = CoreLabel(text=self.value_str(self.slot_value(index)),
                          font_size=self.font_size, **kw)
        label.refresh()
        return label.texture
    
class CyclicSlot(Slot):
    cycle = NumericProperty(10)
    zero_indexed = BooleanProperty(False)
    @property
    def first_value(self):
        return 0 if self.zero_indexed else 1
    def slot_value(self, index):
        cycle = self.cycle
        val = index % cycle + 1 - self.zero_indexed
        val = Slot.slot_value(self, val)
        if val >= cycle + 1 - self.zero_indexed:
            val -= cycle
        return val
    def index_of(self, val, current_index, *args, **kw):
        '''returns the closest index to ``current_index`` that would correspond
        to ``val``. All indices should be localized.'''
        if self.int_valued:
            val = int(round(val))
        zero_indexed = self.zero_indexed
        cycle = self.cycle
        if not (1 - zero_indexed) <= val <= cycle - zero_indexed:
            raise ValueError('value must be between {} and {}; {} is given'.
                             format(1 - zero_indexed, cycle - zero_indexed, val))
        base_index = val - 1 + self.zero_indexed
        n = round((current_index - base_index) / cycle)
        index = n * cycle + base_index
        return index 
        
class TimeSlot(TimeTick, Slot):
    format_str_dict = {'second': '%S',
                        'minute': '%M',
                        'hour': '%H',
                        'day': '%d'}
    _format_str = StringProperty(None, allownone=True)
    tick_size = ListProperty([0, 0])
    def get_format_str(self):
        return self.format_str_dict[self.mode]
    def set_format_str(self, val):
        self._format_str = val
    format_str = AliasProperty(get_format_str, set_format_str, 
                               bind=['mode', '_format_str'])
    '''The format string for the time displayed. By default it is given
    by the corresponding entry in :attr:`format_str_dict`. But it can be
    customized by setting it to the desired string. 
    
    To get the default format back, call :meth:`reset_format_str`.
    '''
    
    def reset_format_str(self, *args):
        self._format_str = None
    def slot_value(self, index, *args, **kw):
        return self.datetime_of(index)
    def get_label_texture(self, index, succinct=True, **kw):
        if isinstance(index, Number):
            t = self.datetime_of(index)
        else:
            t = index
        label = CoreLabel(text=t.strftime(self.format_str),
                         font_size=self.font_size)
        label.refresh()
        return label.texture

mode_options = TimeTick.mode_options

class SecondSlot(TimeSlot):
    mode = OptionProperty('second', options=mode_options)

class MinuteSlot(TimeSlot):
    mode = OptionProperty('minute', options=mode_options)

class HourSlot(TimeSlot):
    mode = OptionProperty('hour', options=mode_options)

class DaySlot(TimeSlot):
    mode = OptionProperty('day', options=mode_options)

#===============================================================================
# Labellers
#===============================================================================

class DatetimeRouletteLabeller(TimeLabeller):
    date_dist_from_edge = NumericProperty('0')
    time_dist_from_edge = NumericProperty('0')
    time_font_size = NumericProperty('18sp')
    date_font_size = NumericProperty('18sp')

#===============================================================================
# Roulettes
#===============================================================================

Builder.load_string('''
<Roulette>:
    canvas.after:
        Color:
            rgb: 1, 1, 1, 0
        Line:
            points: self.x, self.y, self.x, self.top
        Line:
            points: self.right, self.y, self.right, self.top
        Color:
            rgba: 1, 1, 1, .3
        Rectangle:
            pos: self.pos
            size: self.width, self.height / 2
    size_hint: None, 1
''')
class Roulette(Tickline):
    __events__ = ('on_centered',)
    tick_cls = ObjectProperty(Slot)
    '''The class of the tick in this roulette. Should be overriden as needed
    by child class.'''
    labeller_cls = ObjectProperty(SlotLabeller)
    zoomable = BooleanProperty(False)
    draw_line = BooleanProperty(False)
    background_color = ListProperty([0.06, .07, .22])
    font_size = NumericProperty('20sp')
    width = NumericProperty('60dp')
    selected_value = ObjectProperty(None)
    format_str = StringProperty('{}')
    int_valued = BooleanProperty(True)
    scroll_effect_cls = ObjectProperty(RouletteScrollEffect)
    drag_threshold = NumericProperty(0)
    center_duration = NumericProperty(.3)
    '''duration for the animation of :meth:`center_on`.''' 
    density = NumericProperty(4.2)
    '''determines how many slots are shown at a time.'''
    def get_rolling_value(self):
        return self.tick.slot_value(self.tick.localize(self.index_mid))
    def set_rolling_value(self, val):
        self.index_mid = self.tick.globalize(val)
    rolling_value = AliasProperty(get_rolling_value,
                                    set_rolling_value,
                                    bind=['index_mid']) 
    '''the val indicated by whatever slot is in the middle of the roulette.
    If the roulette is still, then :attr:`rolling_value` is equal to
    :attr:`selected_value`. Otherwise, they shouldn't be equal.
    
    .. note::
        This property is not stable under resizing, since often that will
        change the slot in the middle.'''
    def get_ticks(self):
        if self.tick:
            return [self.tick]
        else:
            return []
    def set_ticks(self, val):
        self.tick = val[0]
    ticks = AliasProperty(get_ticks, set_ticks, bind=['tick'])
    # needs a non-None value to so that kv bindings work
    tick = ObjectProperty(None)
    
    def __init__(self, **kw):
        self.tick = Slot()
        super(Roulette, self).__init__(**kw)
        self.scale = dp(10)
        self._trigger_set_selection = \
                Clock.create_trigger(self.set_selected_value)
        self.tick = self.tick_cls()
        self._trigger_calibrate()
    def on_tick_cls(self, *args):
        self.tick = self.tick_cls()
    def on_tick(self, *args):
        tick = self.tick
        if tick:
            tick.font_size = self.font_size
            tick.int_valued = self.int_valued
            tick.format_str = self.format_str
     
    def get_anchor(self):
        '''returns a legal stopping value for the :class:`RouletteScrollEffect`.
        Should be overriden if necessary.'''
        return 0
    def _update_effect_constants(self, *args):
        if not super(Roulette, self)._update_effect_constants(*args):
            return
        effect = self.scroll_effect
        scale = self.scale
        effect.pull_back_velocity = sp(50) / scale
    def calibrate_scroll_effect(self, *args, **kw):
        if not super(Roulette, self).calibrate_scroll_effect(*args, **kw):
            return
        anchor = self.get_anchor()
        effect = self.scroll_effect
        effect.interval = 1. / self.tick.scale_factor
        effect.anchor = anchor
        effect.on_coasted_to_stop = self._trigger_set_selection
    def set_selected_value(self, *args):
        '''set :attr:`selected_value` to the currently slot.'''
        self.selected_value = self.round_(self.rolling_value)      
    def round_(self, val):
        '''round an arbitrary rolling value to a legal selection value. 
        Should be overriden if necessary.'''
        if self.int_valued:
            return int(round(val))            
        return round(val)
    def recenter(self, *args):
        if self.selected_value is not None:
            self.center_on(self.selected_value)
        self._trigger_calibrate()
    def on_size(self, *args):
        self.scale = self.line_length / self.density
        self.recenter()
    def index_of(self, val):
        '''returns the index that should be equivalent to a selection value
        ``val``. Should be overriden if necessary.'''
        return val
    def center_on(self, val, animate=True):
        Animation.stop_all(self)
        center_index = self.index_of(val)
        print hasattr(Tickline, 'max_pos')
        half_length = self.line_length / 2. / self.scale 
        index_0 = center_index - half_length
        index_1 = center_index + half_length
        if animate:
            anim = Animation(index_0=index_0, index_1=index_1, 
                             duration=self.center_duration)
            anim.on_complete = lambda *args: self._centered()
            anim.start(self)
        else:
            self.index_0 = index_0
            self.index_1 = index_1
            self._centered()
    def on_centered(self, *args):
        '''event that fires when the operation :meth:`center_on` completes.
        (and by extension, when :meth:`center` or :meth:`select_and_center`
        completes). By default it doesn't do anything.'''
        pass
    
    def _centered(self, *args):
        print 'animation complete: calling "_centered"'
        self._trigger_calibrate()
        self.dispatch('on_centered')
    def center(self, animate=True):
        self.center_on(self.selected_value, animate)
    def select_and_center(self, val, *args, **kw):
        '''set :attr:`selected_value` to ``val`` and center on it. If 
        :attr:`selected_value` is already ``val``, return False; else return
        True.'''
        if self.selected_value == val:
            return False
        self.selected_value = val
        self.center(*args, **kw)
        return True
    def is_rolling(self):
        return self.scroll_effect.velocity != 0
    def on_int_valued(self, *args):
        if self.tick:
            self.tick.int_valued = self.int_valued
    def on_format_str(self, *args):
        if self.tick:
            self.tick.format_str = self.format_str
            
class CyclicRoulette(Roulette):
    tick_cls = ObjectProperty(CyclicSlot)
    cycle = NumericProperty(10)
    zero_indexed = BooleanProperty(False)
    format_str = StringProperty('{}')
    int_valued = BooleanProperty(True)
    
    def __init__(self, **kw):
        super(CyclicRoulette, self).__init__(**kw)
        self.selected_value = self.tick.first_value
        self.center() 
     
    def on_tick(self, *args):
        tick = self.tick
        if tick:
            tick.cycle = self.cycle
            tick.zero_indexed = self.zero_indexed
            tick.format_str = self.format_str
            tick.int_valued = self.int_valued
    def on_cycle(self, *args):
        if self.tick:
            self.tick.cycle = self.cycle
    def on_zero_indexed(self, *args):
        if self.tick:
            self.tick.zero_indexed = self.zero_indexed
    def index_of(self, val):
        tick = self.tick
        if not tick:
            return val
        return tick.index_of(val, tick.localize(self.index_mid))        
    
class TimeRoulette(Roulette, Timeline):
    '''The base class for implementation of time roulettes where the internals
    keep track of the absolute time, instead of just the value displayed.'''
    tick_cls = ObjectProperty(SecondSlot)
    def __init__(self, **kw):
        super(TimeRoulette, self).__init__(**kw)
        self.tick = self.tick_cls()
        self._trigger_calibrate()
        self.selected_value = self.truncate_datetime(local_now())
        self.center_on(self.selected_value)
    def index_of(self, *args):
        return Timeline.index_of(self, *args)
    def round_(self, val, *args):
        return round_time(val, self.tick.mode)
    def truncate_datetime(self, dt):
        '''method for truncating ``dt`` to the precision corresponding to
        this :class:`TimeRoulette`.'''
        raise NotImplementedError
    
Builder.load_string('''
<TimeFormatCyclicRoulette>:
    zero_indexed: True
    format_str: '{:02d}'
''')
class TimeFormatCyclicRoulette(CyclicRoulette):
    pass

class SecondRoulette(TimeRoulette):
    tick_cls = ObjectProperty(SecondSlot)
    def truncate_datetime(self, dt):
        return dt.replace(microsecond=0)    
        
class MinuteRoulette(TimeRoulette):
    tick_cls = ObjectProperty(MinuteSlot)
    def truncate_datetime(self, dt):
        return dt.replace(second=0, microsecond=0)
    
class HourRoulette(TimeRoulette):
    tick_cls = ObjectProperty(HourSlot)
    def truncate_datetime(self, dt):
        return dt.replace(minute=0, second=0, microsecond=0)
    
class DayRoulette(TimeRoulette):
    tick_cls = ObjectProperty(DaySlot)
    def truncate_datetime(self, dt):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
if __name__ == '__main__':
    b = BoxLayout(
#                   size=[500, 300], size_hint=[None, None],
#                   pos_hint={'x': .1, 'y': .1}
                  )
    b.add_widget(CyclicRoulette(cycle=24, zero_indexed=True, format_str='{:02d}'))
    b.add_widget(CyclicRoulette(cycle=60, zero_indexed=True, format_str='{:02d}'))
    b.add_widget(CyclicRoulette(cycle=60, zero_indexed=True, format_str='{:02d}'))
#     year = Roulette()
#     year.select_and_center(2013)
#     b.add_widget(year)
    b.add_widget(TimeFormatCyclicRoulette(cycle=24))
#     b.add_widget(HourRoulette())
#     b.add_widget(MinuteRoulette())
#     b.add_widget(SecondRoulette())
# #     for i in xrange(5):
#         b.add_widget(SecondRoulette())
    runTouchApp(b)
    
