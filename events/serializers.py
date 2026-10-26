from rest_framework import serializers


class SessionInSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=100)
    session_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()

    def validate(self, data):
        if data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError("end_time must be after start_time")
        return data


class EventCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    cat_id = serializers.IntegerField()
    fee = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0, default=0)
    max_seats = serializers.IntegerField(min_value=1)
    reg_deadline = serializers.DateField()
    sessions = SessionInSerializer(many=True, allow_empty=False)


class DecisionSerializer(serializers.Serializer):
    remarks = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
