from django.db import models


class DietPlan(models.Model):
    summary = models.CharField(max_length=255)
    diet_type = models.CharField(max_length=100)
    goal_calories = models.PositiveIntegerField()
    protein_target = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Diet plan'
        verbose_name_plural = 'Diet plans'

    def __str__(self) -> str:
        return f'{self.summary} ({self.diet_type})'


class ActivityPlan(models.Model):
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Activity plan'
        verbose_name_plural = 'Activity plans'

    def __str__(self) -> str:
        return 'Activity Plan'


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


class Surgery(models.Model):
    class RiskLevels(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=255)
    risk_level = models.CharField(max_length=10, choices=RiskLevels.choices)
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.CASCADE,
        related_name='surgeries',
        null=True,
        blank=True,
    )
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
    patient = models.ForeignKey(
        'patients.Patient',
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
        return f'{self.name} for {self.patient}'
