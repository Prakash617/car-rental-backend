from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class StandardLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "success": True,
                "data": data,
                "pagination": {
                    "count": self.count,
                    "limit": self.limit,
                    "offset": self.offset,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            }
        )
