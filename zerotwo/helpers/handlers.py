from zerotwo import ALLOW_EXCL, OWNER_ID

import re
from inspect import isawaitable
from typing import Optional, Tuple, List, Dict, Union
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler
from telegram.ext import filters as filters_module
from pyrate_limiter import (
    BucketFullException,
    Duration,
    Rate,
    Limiter,
    InMemoryBucket,
)

if ALLOW_EXCL:
    CMD_STARTERS = ("/", "!")
else:
    CMD_STARTERS = ("/",)

class AntiSpam:
    def __init__(self):
        # Custom rate durations
        Duration.CUSTOM = 15  # 15 seconds

        # Define limits
        self.sec_limit = Rate(6, Duration.CUSTOM)   # 6 per 15s
        self.min_limit = Rate(20, Duration.MINUTE)  # 20 per minute
        self.hour_limit = Rate(100, Duration.HOUR)  # 100 per hour
        self.daily_limit = Rate(1000, Duration.DAY) # 1000 per day

        # Pass all rates as a list — Limiter will create InMemoryBucket internally
        self.limiter = Limiter(
            [self.sec_limit, self.min_limit, self.hour_limit, self.daily_limit],
            raise_when_fail=True
        )

    def check_user(self, user):
        """
        Return True if user should be ignored, else False.
        """
        if user == OWNER_ID:
            return False

        acquired = self.limiter.try_acquire(str(user))

        # Handle async/sync automatically
        if isawaitable(acquired):
            async def _async_check():
                try:
                    return not await acquired  # True means rate-limited
                except BucketFullException:
                    return True
            return _async_check()
        else:
            try:
                return not acquired
            except BucketFullException:
                return True


SpamChecker = AntiSpam()
MessageHandlerChecker = AntiSpam()


class CustomCommandHandler(CommandHandler):
    def __init__(self, command, callback, **kwargs):
        super().__init__(command, callback, **kwargs)

        if isinstance(command, str):
            commands = frozenset({command.lower()})
        else:
            commands = frozenset(x.lower() for x in command)
        for comm in commands:
            if not re.match(r"^[\da-z_]{1,32}$", comm):
                raise ValueError(f"Command `{comm}` is not a valid bot command")
        self.commands = commands


    def check_update(self, update) -> Optional[Union[bool, Tuple[List[str], Optional[Union[bool, Dict]]]]]:
        if isinstance(update, Update) and update.effective_message:
            message = update.effective_message

            try:
                user_id = update.effective_user.id
            except:
                user_id = None

            if message.text and len(message.text) > 1:
                fst_word =  message.text.split(None, 1)[0]
                if len(fst_word) > 1 and any(
                    fst_word.startswith(start) for start in CMD_STARTERS
                ):

                    args =  message.text.split()[1:]
                    command_parts = fst_word[1:].split("@")
                    command_parts.append(message.get_bot().username)
                    if user_id == 1087968824:
                        user_id = update.effective_chat.id
                    if not (
                        command_parts[0].lower() in self.commands
                        and command_parts[1].lower() == message.get_bot().username.lower()
                    ):
                        return None
                    if SpamChecker.check_user(user_id):
                        return None
                    filter_result = self.filters.check_update(update)
                    if filter_result:
                        return args, filter_result
                    return False
        return None

    def handle_update(self, update, application, check_result, context=None):
            if context:
                self.collect_additional_context(context, update, application, check_result)
                return self.callback(update, context)
            else:
                optional_args = self.collect_optional_args(application, update, check_result)
                return self.callback(application.bot, update, **optional_args)

    def collect_additional_context(
        self,
        context,
        update,
        application,
        check_result: Optional[Union[bool, Tuple[List[str], Optional[bool]]]],
    ) -> None:
        if isinstance(check_result, tuple):
            context.args = check_result[0]
            if isinstance(check_result[1], dict):
                context.update(check_result[1])
                if isinstance(check_result[1], dict):
                    context.update(check_result[1])



class CustomMessageHandler(MessageHandler):
    def __init__(
        self, filters, 
        callback, 
        block, 
        friendly="", 
        allow_edit=False, 
        **kwargs
    ):
        super().__init__(filters, callback, block=block, **kwargs)
        if allow_edit is False:
            self.filters &= ~(
                filters_module.UpdateType.EDITED_MESSAGE | filters_module.UpdateType.EDITED_CHANNEL_POST
            )

        def check_update(self, update):
            if isinstance(update, Update) and update.effective_message:
                return self.filters(update)