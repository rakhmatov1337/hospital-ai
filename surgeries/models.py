from django.db import models
from django.utils import timezone


class DietPlan(models.Model):
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.CASCADE,
        related_name='diet_plans',
        null=True,
        blank=True,
    )
    summary = models.CharField(max_length=255)
    diet_type = models.CharField(max_length=100)
    goal_calories = models.PositiveIntegerField()
    protein_target = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Diet plan'
        verbose_name_plural = 'Diet plans'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.summary} ({self.diet_type})'


class ActivityPlan(models.Model):
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.CASCADE,
        related_name='activity_plans',
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Activity plan'
        verbose_name_plural = 'Activity plans'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Activity Plan ({self.hospital.name if self.hospital else "No Hospital"})'


class DietPlanFoodItem(models.Model):
    class Categories(models.TextChoices):
        ALLOWED = 'allowed', 'Allowed'
        FORBIDDEN = 'forbidden', 'Forbidden'

    plan = models.ForeignKey(
        DietPlan,
        on_delete=models.CASCADE,
        related_name='food_items',
    )
    category = models.CharField(max_length=20, choices=Categories.choices)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self) -> str:
        return f'{self.get_category_display()}: {self.name}'


class DietPlanMeal(models.Model):
    plan = models.ForeignKey(
        DietPlan,
        on_delete=models.CASCADE,
        related_name='meals',
    )
    meal_type = models.CharField(max_length=50)
    description = models.TextField()
    time = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['meal_type', 'time']

    def __str__(self) -> str:
        return f'{self.meal_type} ({self.plan})'


class ActivityPlanItem(models.Model):
    class Categories(models.TextChoices):
        ALLOWED = 'allowed', 'Allowed'
        RESTRICTED = 'restricted', 'Restricted'

    plan = models.ForeignKey(
        ActivityPlan,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    category = models.CharField(max_length=20, choices=Categories.choices)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self) -> str:
        return f'{self.get_category_display()}: {self.name}'


class SurgeryType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Surgery Type'
        verbose_name_plural = 'Surgery Types'

    def __str__(self) -> str:
        return self.name


class Surgery(models.Model):
    class PriorityLevels(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.ForeignKey(
        SurgeryType,
        on_delete=models.SET_NULL,
        related_name='surgeries',
        null=True,
        blank=True,
    )
    priority_level = models.CharField(max_length=10, choices=PriorityLevels.choices)
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.CASCADE,
        related_name='surgeries',
        null=True,
        blank=True,
    )
    diet_plan = models.ForeignKey(
        DietPlan,
        on_delete=models.SET_NULL,
        related_name='surgeries',
        null=True,
        blank=True,
    )
    activity_plan = models.ForeignKey(
        ActivityPlan,
        on_delete=models.SET_NULL,
        related_name='surgeries',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Medication(models.Model):
    surgery = models.ForeignKey(
        Surgery,
        on_delete=models.CASCADE,
        related_name='medications',
    )
    name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=255)
    frequency = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['start_date']

    def __str__(self) -> str:
        return f'{self.name} for {self.surgery}'
