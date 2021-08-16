def get_activity_response(activities):
    sorted_activity = []
    for activ in activities:
        try:
            user_from = getattr(activ, "user")
        except AttributeError:
            user_from = getattr(activ, "old_owner")

        try:
            user_to = getattr(activ, "whom_follow")
        except AttributeError:
            try:
                user_to = getattr(activ, "new_owner")
            except AttributeError:
                user_to = None
        try:
            price = getattr(activ, "price")
        except AttributeError:
            price = ""

        if price:
            price = price / activ.token.currency.get_decimals

        try:
            quantity = getattr(activ, "quantity")
        except AttributeError:
            quantity = None

        item = {
            "token_id": activ.token.id if activ.token else None,
            "token_image": activ.token.media if activ.token else None,
            "token_name": activ.token.name if activ.token else None,
            "method": activ.method,
            "from_id": user_from.id if user_from else None,
            "from_image": user_from.avatar if user_from else None,
            "from_address": user_from.username if user_from else None,
            "from_name": user_from.display_name if user_from else None,
            "to_id": user_to.id if user_to else None,
            "to_image": user_to.avatar if user_to else None,
            "to_address": user_to.username if user_to else None,
            "to_name": user_to.display_name if user_to else None,
            "date": activ.date,
            "price": price,
            "quantity": quantity,
        }
        if item not in sorted_activity:
            sorted_activity.append(item)
    return sorted_activity
