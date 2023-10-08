
students = [
    {
        "name": "Alice",
        "grades": {
            "Math": 85,
            "Science": 92,
            "History": 78,
            "English": 88
        }
    },
    {
        "name": "Bob",
        "grades": {
            "Math": 59,
            "Science": 74,
            "History": 65,
            "English": 70
        }
    },
    {
        "name": "Charlie",
        "grades": {
            "Math": 90,
            "Science": 85,
            "History": 80,
            "English": 82
        }
    },
    {
        "name": "Daisy",
        "grades": {
            "Math": 72,
            "Science": 88,
            "History": 83,
            "English": 76
        }
    },
    {
        "name": "Eve",
        "grades": {
            "Math": 78,
            "Science": 80,
            "History": 88,
            "English": 89
        }
    },
    {
        "name": "Frank",
        "grades": {
            "Math": 92,
            "Science": 91,
            "History": 90,
            "English": 88
        }
    }
]


def get_student_grade(student_name,subject):
    for student in students:
        if student["name"] == student_name:
            return student["grades"][subject]
    return None



print(get_student_grade("Frank","Math"))    

def get_student_average(student_name):
    student = [student for student in students if student["name"] == student_name]
    gpt_student = next(s for s in students if s["name"] == student_name)
    grades = gpt_student["grades"].values()
    avg = sum(grades) / len(grades)
    return avg

print(get_student_average("Frank"))

def get_subject_average(subject):
    
    pass

def get_highest_grade(subject):
    pass

def add_student(name):
    pass

def add_grade(student_name,subject,grade):
    pass

# Bonus
def get_class_average():
    pass
